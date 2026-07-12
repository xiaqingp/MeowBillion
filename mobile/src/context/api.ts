export type ContextKind = 'travel' | 'rental';

export function contextRequestPath(kind: ContextKind, resource: 'analysis' | 'items') {
  if (kind === 'travel') return resource === 'analysis' ? '/api/travel_analysis' : '/api/trips';
  return resource === 'analysis' ? '/api/rental_analysis' : '/api/rental_properties';
}

export function contextWrite(id: string, body: Record<string, unknown>, kind: ContextKind = 'travel') {
  return { path: `${kind === 'travel' ? '/api/trips' : '/api/rental_properties'}/${encodeURIComponent(id)}`, method: 'PATCH' as const, body };
}
