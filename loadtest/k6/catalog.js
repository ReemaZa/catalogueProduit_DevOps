// Test de charge k6 : 3 scénarios (ramp-up 100 VU, stress 500 VU, spike 1500 VU / 30 s).
// Lancer :  k6 run loadtest/k6/catalog.js
// Incident simulé (beaucoup d'erreurs) :  k6 run -e FLAKY_SHARE=0.4 loadtest/k6/catalog.js
// Test rapide (5 % des VU) :  k6 run -e SCALE=0.05 loadtest/k6/catalog.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8080';
const SCALE = parseFloat(__ENV.SCALE || '1');
// Part du trafic envoyée sur /flaky (qui échoue 30 % du temps) : 1 % = trafic sain, 40 % = incident.
const FLAKY_SHARE = parseFloat(__ENV.FLAKY_SHARE || '0.01');
const CHECKOUT_SHARE = 0.10;
const vus = (n) => Math.max(1, Math.round(n * SCALE));

// Pour le SLI, un code < 500 est un succès (404/409 = erreur client, pas une panne).
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 499 }));

export const options = {
  scenarios: {
    // 1) Ramp-up : 0 -> 100 VU en 1 min, puis palier 1 min
    ramp_up: {
      executor: 'ramping-vus', startTime: '0s', startVUs: 0, gracefulRampDown: '10s',
      stages: [{ duration: '1m', target: vus(100) }, { duration: '1m', target: vus(100) }],
    },
    // 2) Stress prolongé à 500 VU
    stress: {
      executor: 'ramping-vus', startTime: '2m15s', startVUs: 0, gracefulRampDown: '10s',
      stages: [
        { duration: '1m', target: vus(500) },
        { duration: '3m', target: vus(500) },
        { duration: '20s', target: 0 },
      ],
    },
    // 3) Spike soudain à 1500 VU pendant 30 s
    spike: {
      executor: 'ramping-vus', startTime: '6m45s', startVUs: 0, gracefulRampDown: '10s',
      stages: [
        { duration: '5s', target: vus(1500) },
        { duration: '30s', target: vus(1500) },
        { duration: '5s', target: 0 },
      ],
    },
  },
  // Les seuils reprennent les SLO du TP (le test "échoue" si le SLO est violé).
  thresholds: {
    http_req_failed: ['rate<0.005'],        // disponibilité 99,5 %
    http_req_duration: ['p(95)<200'],       // latence p95 <= 200 ms
  },
};

const JSON_HEADERS = { headers: { 'Content-Type': 'application/json' } };

// Exécuté une fois : crée un produit avec un gros stock pour que /checkout fonctionne.
export function setup() {
  const body = JSON.stringify({ name: `k6-produit-${Date.now()}`, price_cents: 1999,
                                category: 'electronics', stock: 10000000 });
  const res = http.post(`${BASE}/products`, body, JSON_HEADERS);
  check(res, { 'produit de test créé': (r) => r.status === 201 });
  return { productId: res.json('id') };
}

export default function (data) {
  const r = Math.random();
  if (r < FLAKY_SHARE) {
    http.get(`${BASE}/flaky`);
  } else if (r < FLAKY_SHARE + CHECKOUT_SHARE) {
    const body = JSON.stringify({ items: [{ product_id: data.productId, quantity: 1 }] });
    http.post(`${BASE}/checkout`, body, { ...JSON_HEADERS, tags: { name: 'checkout' } });
  } else if (r < 0.6) {
    http.get(`${BASE}/products?limit=20`);
  } else {
    http.get(`${BASE}/products/${data.productId}`, { tags: { name: 'product_by_id' } });
  }
  sleep(0.2 + Math.random() * 0.3);
}
