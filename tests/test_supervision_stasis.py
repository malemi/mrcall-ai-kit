import json
import os
from pathlib import Path
import shlex
import unittest

import test_supervision_transport as transport_tests
import test_supervision_local_goals as local


EVIDENCE = Path('/tmp/mrcall-ai-kit/goal-stasis-20261101/execute')
WRAPPER = """python3 - <<'PY'
import sys
sys.path.insert(0,'/fixture/goals/code')
from goal_client import request
s='/fixture/control.sock'; i='fixture'
d=request(s,{'op':'inspect','id':i})['result']
r=request(s,{'op':'report','id':i,'generation':d['generation'],'report':{'outcome':'blocked'}})
print({'report_ok':r['ok']})
PY"""

CONDITIONAL_COMMAND = '/bin/bash -lc "python3 - <<\'PY\'\nimport sys,json\nsys.path.insert(0,\'/fixture/goals/code\')\nfrom goal_client import request\ns=\'/fixture/goals/control.sock\'; i=\'fixture\'\nd=request(s,{\'op\':\'inspect\',\'id\':i})[\'result\']\nprint(json.dumps({k:d.get(k) for k in (\'id\',\'generation\',\'status\')}))\nif d.get(\'generation\')==3 and d.get(\'status\')"\'!=\'"\'stopped\':\n r=request(s,{\'op\':\'report\',\'id\':i,\'generation\':3,\'report\':{\'state\':\'blocked_on_unchanged_authority\',\'remaining\':\'Operator authority remains required.\',\'action\':\'Preserve failures and operator limits.\'}})\n print(json.dumps({\'report_ok\':r[\'ok\']}))\nPY"'
CONDITIONAL_WRAPPER = shlex.split(CONDITIONAL_COMMAND)[2]

REPORTING_COMMANDS = ('/bin/bash -lc "python3 - <<\'PY\'\nimport sys,json\nsys.path.insert(0,\'/fixture/goals/code\')\nfrom goal_client import request\ns=\'/fixture/goals/control.sock\'\nd=request(s,{\'op\':\'inspect\',\'id\':\'fixture\'})[\'result\']\nprint(json.dumps({\'generation\':d.get(\'generation\'),\'status\':d.get(\'status\'),\'fields\':list(d)}))\nfor k in (\'latest_report\',\'last_report\',\'scope\',\'authorized_scope\'):\n if k in d: print(json.dumps({k:d[k]}))\nPY"', '/bin/bash -lc "python3 - <<\'PY\'\nimport sys,json\nsys.path.insert(0,\'/fixture/goals/code\')\nfrom goal_client import request\ns=\'/fixture/goals/control.sock\';i=\'fixture\'\nd=request(s,{\'op\':\'inspect\',\'id\':i})[\'result\']\nr=d.get(\'reports\',[])\nprint(json.dumps({\'latest_report\':r[-1:] if isinstance(r,list) else r,\'pending_obligation\':d.get(\'pending_obligation\')})[:5000])\nprint(request(s,{\'op\':\'report\',\'id\':i,\'generation\':d[\'generation\'],\'report\':{\'state\':\'blocked_on_unchanged_authority\',\'remaining\':\'Operator authority remains required.\',\'action\':\'Preserve failures and operator limits.\'}})[\'ok\'])\nPY"')
REPORTING_WRAPPERS = tuple(shlex.split(command)[2] for command in REPORTING_COMMANDS)


def reporting_items():
    return [{**report_item(), 'id': 'reporting-' + str(index), 'command': command}
            for index, command in enumerate(REPORTING_COMMANDS)]


def conditional_report_item():
    return {**report_item(), 'command': CONDITIONAL_COMMAND}


def report_item():
    return {'id': 'report-command', 'type': 'commandExecution', 'status': 'completed',
            'command': '/bin/bash -lc ' + shlex.quote(WRAPPER)}


class ActivityTests(unittest.TestCase):
    setUp = transport_tests.TransportTests.setUp
    tearDown = transport_tests.TransportTests.tearDown
    respond = transport_tests.TransportTests.respond
    server = transport_tests.TransportTests.server

    def reconcile(self, items, newer=None, status='completed'):
        def history(method, params):
            if method == 'thread/turns/list':
                self.assertEqual(params['sortDirection'], 'desc')
                if 'cursor' not in params:
                    return {'data': newer or [], 'nextCursor': 'anchor-page'}
                return {'data': [{'id': 'anchor-turn', 'status': status, 'items': [
                    {'type': 'userMessage', 'clientId': self.event}, *items]}], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(history) as transport:
            result = transport.reconcile(self.thread_id, self.event, include_activity=True)['activity']
        (self.root / 'control.sock').unlink()
        return result

    def test_incident_report_wrapper_and_prose_are_no_work_across_pages(self):
        activity = self.reconcile([report_item(), {'type': 'agentMessage', 'text': 'I made substantial progress'}])
        self.assertEqual(activity['classification'], 'no_work')
        self.assertEqual(activity['turn_ids'], ['anchor-turn'])
        self.assertTrue(any(params.get('cursor') == 'anchor-page' for method, params in self.calls))
        self.assertNotIn('substantial', json.dumps(activity))

    def test_live_conditional_report_with_dictionary_summary_is_no_work(self):
        activity = self.reconcile([conditional_report_item()])
        self.assertEqual(activity['classification'], 'no_work')
        for source in (CONDITIONAL_WRAPPER.replace("d.get('generation')==3 and d.get('status')!='stopped'", "not (d.get('status') == 'stopped') or d.get('generation') in (2, 3)"),
                       CONDITIONAL_WRAPPER.replace("for k in ('id','generation','status')", "for k in ['id','generation','status'] if k != 'status'")):
            self.assertTrue(transport_tests.module.bookkeeping_command(['/bin/bash', '-lc', source]))

    def test_live_reporting_loop_type_guard_and_slices_are_no_work(self):
        self.assertEqual(self.reconcile(reporting_items())['classification'], 'no_work')
        for source in (REPORTING_WRAPPERS[1].replace('isinstance(r,list)', 'isinstance(r,(list,tuple))'),
                       REPORTING_WRAPPERS[1].replace('r[-1:]', 'r[-1::+1]')):
            self.assertTrue(transport_tests.module.bookkeeping_command(['/bin/bash', '-lc', source]))

    def test_literal_json_formatting_is_bookkeeping_and_callable_hooks_are_execution(self):
        formatted = CONDITIONAL_WRAPPER.replace("print(json.dumps({'report_ok':r['ok']}))", "print(json.dumps({'report_ok':r['ok']}, sort_keys=True, indent=2, separators=(',', ':')))" )
        self.assertTrue(transport_tests.module.bookkeeping_command(['/bin/bash', '-lc', formatted]))
        for options in ("default=open", "sort_keys=open('/tmp/work','w').write('work')", "**{'sort_keys':True}"):
            source = CONDITIONAL_WRAPPER.replace("print(json.dumps({'report_ok':r['ok']}))", "print(json.dumps({'report_ok':r['ok']}, " + options + '))')
            self.assertFalse(transport_tests.module.bookkeeping_command(['/bin/bash', '-lc', source]))

    def test_mixed_work_in_reporting_loops_type_guards_and_slices_is_execution(self):
        for source in (REPORTING_WRAPPERS[0].replace('if k in d: print(json.dumps({k:d[k]}))', "if k in d: open('/tmp/work','w').write(k)"),
                       REPORTING_WRAPPERS[0].replace("for k in ('latest_report','last_report','scope','authorized_scope'):", "for k in list(d):"),
                       REPORTING_WRAPPERS[0].replace('if k in d: print(json.dumps({k:d[k]}))', "if k in d: print(k)\n else: open('/tmp/work','w').write(k)"),
                       REPORTING_WRAPPERS[0].replace("for k in ('latest_report','last_report','scope','authorized_scope'):", 'while True:'),
                       REPORTING_WRAPPERS[1].replace('isinstance(r,list)', "isinstance(open('/tmp/work','w').write('work'),list)"),
                       REPORTING_WRAPPERS[1].replace('else r', "else open('/tmp/work','w').write('work')"),
                       REPORTING_WRAPPERS[1].replace('r[-1:]', "r[:open('/tmp/work','w').write('work')]"),
                       REPORTING_WRAPPERS[1].replace("r=d.get('reports',[])", "list=d.get('reports',[])\nr=list"),
                       REPORTING_WRAPPERS[1].replace('isinstance(r,list)', 'isinstance(r,custom_type)')):
            item = {**report_item(), 'command': ['/bin/bash', '-lc', source]}
            self.assertEqual(self.reconcile([item])['classification'], 'execution')

    def test_mixed_work_in_conditional_and_comprehension_is_execution(self):
        for source in (CONDITIONAL_WRAPPER.replace(" print(json.dumps({'report_ok':r['ok']}))", " open('/tmp/work','w').write('work')"),
                       CONDITIONAL_WRAPPER.replace("\nPY", "\nelse:\n open('/tmp/work','w').write('work')\nPY"),
                       CONDITIONAL_WRAPPER.replace("d.get('generation')==3", "open('/tmp/work','w').write('work')==3"),
                       CONDITIONAL_WRAPPER.replace('k:d.get(k)', "k:open('/tmp/work','w').write(k)"),
                       CONDITIONAL_WRAPPER.replace("for k in ('id','generation','status')", "for k in ('id','generation','status') if open('/tmp/work','w').write(k)"),
                       CONDITIONAL_WRAPPER.replace("for k in ('id','generation','status')", "for k in d.get('keys')"),
                       CONDITIONAL_WRAPPER.replace("for k in ('id','generation','status')", "for k in ('id',) for other in ('status',)")):
            item = {**conditional_report_item(), 'command': ['/bin/bash', '-lc', source]}
            self.assertEqual(self.reconcile([item])['classification'], 'execution')

    def test_mixed_wrapper_and_other_commands_are_execution(self):
        for source in (WRAPPER.replace("print({'report_ok':r['ok']})", "open('/tmp/work','w').write('work')"),
                       WRAPPER + '\nprintf work', 'python3 -c "print(42)"'):
            item = report_item()
            item['command'] = ['/bin/bash', '-lc', source]
            self.assertEqual(transport_tests.module.public_activity([
                {'id': 'mixed', 'status': 'completed', 'items': [item]}])['classification'], 'execution')

    def test_shell_expansion_and_mixed_control_cli_are_execution(self):
        for source in (WRAPPER.replace("<<'PY'", '<<PY').replace("'/fixture/control.sock'", "'$(touch /tmp/work)'"),
                       WRAPPER.replace("<<'PY'", "<<'P'Y"),
                       WRAPPER.replace('python3 -', '$(touch /tmp/work)/python3 -'),
                       WRAPPER.replace("{'op':'report','id':i", "{'op':'report','op':i,'id':i")):
            self.assertFalse(transport_tests.module.bookkeeping_command(['/bin/bash', '-lc', source]))
        direct = "python3 -I /fixture/goal_client.py --socket /fixture/control.sock request " + shlex.quote(json.dumps({'op': 'report', 'id': 'fixture'}))
        self.assertTrue(transport_tests.module.bookkeeping_command(direct))
        self.assertFalse(transport_tests.module.bookkeeping_command(direct + '; touch /tmp/work'))

    def test_newer_execution_and_active_turns_prevent_no_work(self):
        for item, expected in (({'type': 'fileChange', 'status': 'completed'}, 'execution'),
                               ({'type': 'commandExecution', 'status': 'inProgress', 'command': 'sleep 3'}, 'active'),
                               ({'type': 'futureUnknownTool'}, 'unknown')):
            activity = self.reconcile([report_item()], [{'id': 'newer', 'status': 'completed', 'items': [item]}])
            self.assertEqual(activity['classification'], expected)
            self.assertEqual(activity['turn_ids'], ['newer', 'anchor-turn'])

    def test_missing_items_failed_turn_and_unrecognized_command_shape_are_unknown(self):
        for items, status in (([{'type': 'commandExecution'}], 'completed'), ([], 'failed'),
                              ([{'type': 'functionCallOutput'}], 'completed')):
            self.assertEqual(self.reconcile(items, status=status)['classification'], 'unknown')

    def test_active_turn_with_only_prose_is_active(self):
        self.assertEqual(self.reconcile([], status='inProgress')['classification'], 'active')

    def test_incomplete_history_never_establishes_stasis_and_legacy_is_unchanged(self):
        def missing(method, params):
            if method == 'thread/turns/list':
                return {'data': [], 'nextCursor': None}
            return self.respond(method, params)
        with self.server(missing) as transport:
            result = transport.reconcile(self.thread_id, self.event, include_activity=True)
            self.assertEqual(result['status'], 'absent')
            self.assertNotIn('activity', result)
        (self.root / 'control.sock').unlink()
        with self.server() as transport:
            self.assertNotIn('activity', transport.reconcile(self.thread_id, self.event))


@unittest.skipIf(os.geteuid() == 0, 'Installed local service requires an ordinary account')
class InstalledStasisTests(unittest.TestCase):
    setUp = local.LocalGoalTests.setUp
    cleanup = local.LocalGoalTests.cleanup
    run_command = local.LocalGoalTests.run_command
    start_service = local.LocalGoalTests.start_service
    stop_service = local.LocalGoalTests.stop_service
    request = local.LocalGoalTests.request
    tick = local.LocalGoalTests.tick
    check_candidate = local.LocalGoalTests.check_candidate
    write_candidate = local.LocalGoalTests.write_candidate
    create_goal = local.LocalGoalTests.create_goal

    def setUp(self):
        local.EVIDENCE = EVIDENCE
        local.LocalGoalTests.setUp(self)

    def failed_and_consumed(self):
        goal, native = self.create_goal()
        failed = self.check_candidate(goal)
        self.assertFalse(failed['last_receipt']['passed'])
        for entry in native.accepted:
            if entry['threadId'] == goal['target']['lead_id']:
                native.history_items[entry['clientUserMessageId']] = [report_item()]
        native.finish_all()
        return goal, native

    def test_installed_combined_live_reporting_captures_produce_corrective_delivery(self):
        goal, native = self.failed_and_consumed()
        for entry in native.accepted:
            if entry['threadId'] == goal['target']['lead_id']:
                native.history_items[entry['clientUserMessageId']] = [conditional_report_item(), *reporting_items()]
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        correction = next(event for event in state['outbox'] if event.get('intervention'))
        activity = correction['intervention']['activity']
        self.assertEqual(activity['classification'], 'no_work')
        self.assertEqual(activity['evidence']['commandExecution:no_work'], 3)
        injected = next(entry['input'][0]['text'] for entry in native.accepted
                        if entry['clientUserMessageId'] == correction['id'])
        self.assertIn('Automatic correction', injected)
        self.assertFalse(state['last_receipt']['passed'])
        self.tick()
        self.assertEqual(len(native.accepted), 4)
        self.log.write(json.dumps({'corrective_event': correction, 'actual_injected_text': injected}) + '\n')

    def test_installed_live_conditional_report_produces_corrective_delivery(self):
        goal, native = self.failed_and_consumed()
        for entry in native.accepted:
            if entry['threadId'] == goal['target']['lead_id']:
                native.history_items[entry['clientUserMessageId']] = [conditional_report_item()]
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        correction = next(event for event in state['outbox'] if event.get('intervention'))
        self.assertEqual(correction['intervention']['activity']['classification'], 'no_work')
        injected = next(entry['input'][0]['text'] for entry in native.accepted
                        if entry['clientUserMessageId'] == correction['id'])
        self.assertIn('Automatic correction', injected)
        self.assertFalse(state['last_receipt']['passed'])
        self.tick()
        self.assertEqual(len(native.accepted), 4)
        self.log.write(json.dumps({'corrective_event': correction, 'actual_injected_text': injected}) + '\n')

    def test_installed_report_only_correction_lost_ack_restart_stop_resume_and_cap(self):
        goal, native = self.failed_and_consumed()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.request({'op': 'set_limits', 'id': goal['id'], 'generation': state['generation'],
                      'limits': {'max_wakeups': 6, 'process_timeout_seconds': 3}})
        native.drop_ack = True
        self.tick()
        corrected = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(len(native.accepted), 4)
        correction = next(event for event in corrected['outbox'] if event.get('intervention'))
        self.assertEqual(correction['status'], 'uncertain')
        self.assertEqual(correction['intervention']['activity']['classification'], 'no_work')
        text = next(entry['input'][0]['text'] for entry in native.accepted
                    if entry['clientUserMessageId'] == correction['id'])
        for required in ('Automatic correction', 'new authorized concrete step', 'precise decision',
                         'Conserve tokens', 'no new spending', 'authorized allowance has been consumed'):
            self.assertIn(required, text)
        self.assertFalse(corrected['last_receipt']['passed'])
        self.stop_service()
        self.start_service()
        self.request({'op': 'stop', 'id': goal['id'], 'generation': corrected['generation']})
        stopped = self.request({'op': 'inspect', 'id': goal['id']})
        self.tick()
        self.assertEqual(len(native.accepted), 4)
        self.request({'op': 'resume', 'id': goal['id'], 'generation': stopped['generation']})
        self.tick()
        self.assertEqual(len(native.accepted), 4)
        reconciled = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(next(e for e in reconciled['outbox'] if e['id'] == correction['id'])['status'], 'delivered')
        native.finish_all()
        self.tick()
        continued = self.request({'op': 'inspect', 'id': goal['id']})
        corrections = [event for event in continued['outbox'] if event.get('intervention')]
        self.assertEqual(len(corrections), 2)
        self.assertEqual(corrections[-1]['intervention']['source_event_id'], correction['id'])
        native.finish_all()
        self.tick()
        limited = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(limited['status'], 'limited')
        self.assertEqual(limited['wakeups_reserved'], 6)
        self.assertFalse(limited['last_receipt']['passed'])
        self.log.write(json.dumps({'corrective_event': correction, 'actual_injected_text': text, 'limited': limited}) + '\n')

    def test_installed_consumed_observation_refreshes_after_missing_history(self):
        goal, native = self.failed_and_consumed()
        native.identities[goal['target']['lead_id']] = 'active'
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        lead = next(event for event in state['outbox'] if event['role'] == 'lead')
        self.assertEqual(lead['observation']['activity']['classification'], 'no_work')
        native.completed.remove(lead['id'])
        native.hide_pending = True
        native.identities[goal['target']['lead_id']] = 'idle'
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(state['last_observation']['lead_activity']['classification'], 'unknown')
        self.assertFalse(any(event.get('intervention') for event in state['outbox']))

    def test_installed_newer_work_suppresses_correction_and_candidate_can_pass(self):
        goal, native = self.failed_and_consumed()
        native.newer_turns = [{'id': 'newer-work', 'status': 'completed', 'items': [
            {'type': 'commandExecution', 'command': 'python3 -c "print(42)"', 'status': 'completed'}]}]
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(state['last_observation']['lead_activity']['classification'], 'execution')
        self.assertFalse(any(event.get('intervention') for event in state['outbox']))
        native.finish_all()
        self.write_candidate('import json\nprint(json.dumps({"value":42}))\n')
        self.assertEqual(self.check_candidate(goal)['status'], 'completed')

    def test_installed_newer_active_turn_defers_lead_despite_idle_metadata(self):
        goal, native = self.failed_and_consumed()
        before = self.request({'op': 'inspect', 'id': goal['id']})
        failed_attempt = before['last_attempt']['id']
        self.request({'op': 'set_limits', 'id': goal['id'], 'generation': before['generation'],
                      'limits': {'max_wakeups': 2, 'process_timeout_seconds': 3}})
        native.newer_turns = [{'id': 'active-work', 'status': 'inProgress', 'items': []}]
        self.tick()
        state = self.request({'op': 'inspect', 'id': goal['id']})
        self.assertEqual(state['last_observation']['lead_activity']['classification'], 'active')
        self.assertEqual(state['status'], 'open')
        self.assertEqual(sum(entry['threadId'] == goal['target']['lead_id'] for entry in native.accepted), 1)
        self.assertEqual(state['last_attempt']['id'], failed_attempt)
        self.assertFalse(any(event.get('intervention') for event in state['outbox']))


if __name__ == '__main__':
    unittest.main()
