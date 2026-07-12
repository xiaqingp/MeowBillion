import assert from 'node:assert/strict';
import test from 'node:test';

import { contextRequestPath, contextWrite } from './api';

test('uses existing travel and rental API paths', () => {
  assert.equal(contextRequestPath('travel', 'analysis'), '/api/travel_analysis');
  assert.equal(contextRequestPath('rental', 'items'), '/api/rental_properties');
  assert.deepEqual(contextWrite('trip_1', { name: 'Paris' }), { path: '/api/trips/trip_1', method: 'PATCH', body: { name: 'Paris' } });
});
