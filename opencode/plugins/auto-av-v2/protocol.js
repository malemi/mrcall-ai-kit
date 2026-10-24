export function snapshot(messages) {
  const users = messages.filter(message => message.type === 'user' && message.metadata?.['auto-av'] !== true);
  const user = users.at(-1);
  const draft = messages.findLast(message => message.type === 'assistant');
  const text = draft?.content?.filter(part => part.type === 'text').map(part => part.text).join('\n') ?? '';
  return user && text.trim() ? { turn: user.id, request: users.map(item => item.text).join('\n'), draft: text } : undefined;
}

export function automaticPrompt(body, input) {
  const lines = body.split('\n');
  if (lines[0] === '---') {
    const end = lines.indexOf('---', 1);
    if (end < 0) throw new Error('unterminated canonical av frontmatter');
    body = lines.slice(end + 1).join('\n').replace(/^\n/, '');
  }
  body = body.replaceAll('$ARGUMENTS', '');
  return `${body}\n\nAutomatic application to the existing assignment follows. This is not a bare av invocation. Apply the stance to the assignment and draft below. Preserve adequate final content unchanged, perform remaining authorized work where feasible, and do not add an av acknowledgment.\n\n${JSON.stringify({ assignment: input.request, draft: input.draft })}`;
}

export function createProtocol(policy, body) {
  const attempted = new Map();
  const applied = new Map();
  const pending = new Map();
  return {
    begin(sessionID, messages) {
      const input = snapshot(messages);
      if (!input || Array.from(input.draft).length <= 300) {
        attempted.delete(sessionID);
        pending.delete(sessionID);
        return;
      }
      if (applied.get(sessionID) === input.turn) return;
      const previous = attempted.get(sessionID);
      if (previous?.turn === input.turn && previous.draft === input.draft) return;
      attempted.set(sessionID, input);
      const entry = { ...input };
      pending.set(sessionID, entry);
      return entry;
    },
    selectorPrompt(entry) {
      return `${policy}\n\n${JSON.stringify({ assignment: entry.request, draft: entry.draft })}`;
    },
    finish(sessionID, entry, output, messages) {
      const current = snapshot(messages);
      if (pending.get(sessionID) !== entry) return;
      if (!current || Array.from(current.draft).length <= 300) {
        attempted.delete(sessionID);
        pending.delete(sessionID);
        return;
      }
      if (current.turn !== entry.turn) return;
      if (typeof output !== 'string' || Buffer.byteLength(output) > 2048 || !['APPLY', 'SKIP'].includes(output.trim())) throw new Error('invalid or oversized selector output');
      if (output.trim() !== 'APPLY') return;
      applied.set(sessionID, entry.turn);
      return automaticPrompt(body, entry);
    },
    dispose(sessionID) {
      attempted.delete(sessionID);
      applied.delete(sessionID);
      pending.delete(sessionID);
    },
    clear(sessionID, entry) {
      if (pending.get(sessionID) === entry) pending.delete(sessionID);
    },
  };
}
