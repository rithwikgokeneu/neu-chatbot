const BASE = '';

async function request(url, opts = {}) {
  const res = await fetch(`${BASE}${url}`, {
    credentials: 'include',
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts.headers },
  });
  if (res.status === 401 || res.status === 302) {
    window.location.href = '/login';
    return null;
  }
  return res;
}

export async function getJSON(url) {
  const res = await request(url);
  return res?.json();
}

export async function postJSON(url, body) {
  const res = await request(url, {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return res?.json();
}

export async function del(url) {
  const res = await request(url, { method: 'DELETE' });
  return res?.json();
}

export async function getUser() {
  try {
    const res = await fetch('/api/me', { credentials: 'include' });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}
