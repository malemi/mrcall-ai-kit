import { Effect, Fiber, Stream } from 'effect';
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { createProtocol } from './protocol.js';

export default {
  id: 'mrcall-auto-av',
  effect(ctx) {
    return Effect.gen(function* () {
      const root = join(process.env.MRCALL_KIT_HOME ?? join(homedir(), '.config/mrcall-ai-kit'), 'auto-av');
      const protocol = yield* Effect.try(() => createProtocol(readFileSync(join(root, 'selector.md'), 'utf8'), readFileSync(join(root, 'av.md'), 'utf8')));
      const running = new Map();
      yield* ctx.session.hook('prompt', event => Effect.gen(function* () {
        if (event.metadata?.['auto-av'] === true) return;
        const fiber = running.get(event.sessionID);
        if (fiber) yield* Fiber.interrupt(fiber);
      }));
      const handle = event => Effect.gen(function* () {
        if (event.type !== 'session.execution.succeeded') return;
        const sessionID = event.data.sessionID;
        const messages = yield* ctx.session.context({ sessionID });
        const entry = protocol.begin(sessionID, messages);
        if (!entry) return;
        yield* Effect.gen(function* () {
          const role = yield* ctx.agent.get({ agentID: 'verify' });
          const model = role.data.model;
          if (!model?.providerID || !model?.id) throw new Error('automatic av requires an explicit model on the installed verify agent');
          const result = yield* ctx.generate.text({ model, prompt: protocol.selectorPrompt(entry) });
          const current = yield* ctx.session.context({ sessionID });
          const text = yield* Effect.try(() => protocol.finish(sessionID, entry, result.text, current));
          if (text) yield* ctx.session.prompt({ sessionID, text, metadata: { 'auto-av': true }, delivery: 'steer' });
        }).pipe(Effect.ensuring(Effect.sync(() => protocol.clear(sessionID, entry))));
      }).pipe(Effect.timeout('30 seconds'), Effect.catchCause(cause => Effect.logWarning('automatic av unavailable', { cause })));
      yield* ctx.event.subscribe().pipe(Stream.runForEach(event => Effect.gen(function* () {
        const sessionID = event.data?.sessionID;
        if (event.type === 'session.execution.interrupted' || event.type === 'session.removed') {
          const fiber = running.get(sessionID);
          if (fiber) yield* Fiber.interrupt(fiber);
          running.delete(sessionID);
          if (event.type === 'session.removed') protocol.dispose(sessionID);
          return;
        }
        if (event.type !== 'session.execution.succeeded' || running.has(sessionID)) return;
        const fiber = yield* handle(event).pipe(Effect.ensuring(Effect.sync(() => running.delete(sessionID))), Effect.forkScoped);
        running.set(sessionID, fiber);
      })), Effect.forkScoped);
    }).pipe(Effect.catchCause(cause => Effect.logWarning('automatic av plugin unavailable', { cause })));
  },
};
