export type StreamChunk = {
  type: 'text' | 'json';
  data: string;
};

export async function* streamQuery(payload: any): AsyncGenerator<StreamChunk> {
  const res = await fetch('/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.body) {
    const text = await res.text();
    yield { type: 'text', data: text };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let done = false;
  while (!done) {
    const { value, done: d } = await reader.read();
    done = d;
    if (value) {
      const chunk = decoder.decode(value, { stream: true });
      yield { type: 'text', data: chunk };
    }
  }
}


