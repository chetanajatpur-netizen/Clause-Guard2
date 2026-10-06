const API_BASE = import.meta.env.VITE_API_URL || '';

async function request(url, options = {}) {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Accept': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error?.error?.message || `Request failed: ${response.status}`);
  }

  return response.json();
}

export async function analyzeContract(file) {
  const formData = new FormData();
  formData.append('file', file);

  return request('/api/v1/analyze', {
    method: 'POST',
    body: formData,
    headers: {},
  });
}

export async function searchDocument(documentId, query, topK = 5) {
  return request('/api/v1/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, query, top_k: topK }),
  });
}

export async function getDocuments() {
  return request('/api/v1/documents');
}

export async function getDocument(id) {
  return request(`/api/v1/documents/${id}`);
}

export async function deleteDocument(id) {
  return request(`/api/v1/documents/${id}`, { method: 'DELETE' });
}

export async function getInsights() {
  return request('/api/v1/insights');
}
