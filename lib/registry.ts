import raw from './generated/registry.json';
import type { Fact, Figure, Ledger, Reference, Registry } from './types';

/**
 * Artifact lookup by global id ("ch1.atus_work_weighted").
 *
 * lib/generated/registry.json is built by scripts/gen-registry.mjs from every
 * app/**\/data/ directory (manifest.json, facts.json, ledger.json, figures/*.json)
 * plus data/references.json. Call these from server components only, so artifact
 * data is rendered into HTML rather than shipped to the browser. Client widgets
 * receive their data as props from a server wrapper.
 *
 * A missing id throws, which fails the static build: a typo'd or deleted fact
 * cannot reach a published page.
 *
 * This API is a contract between the front-end and widget agents. Internals may
 * change; the exported names and signatures may not.
 */
const registry = raw as unknown as Registry;

function lookup<T>(table: Record<string, T>, kind: string, id: string): T {
  const hit = table[id];
  if (hit === undefined) {
    throw new Error(`Unknown ${kind} "${id}". Is it exported from Box and registered (scripts/gen-registry.mjs)?`);
  }
  return hit;
}

export const getFact = (id: string): Fact => lookup(registry.facts, 'fact', id);
export const getLedger = (id: string): Ledger => lookup(registry.ledgers, 'ledger', id);
export const getReference = (id: string): Reference => lookup(registry.references, 'reference', id);

export function getFigure<T extends Figure = Figure>(id: string): T {
  return lookup(registry.figures, 'figure', id) as T;
}

export const hasFact = (id: string): boolean => id in registry.facts;
export const hasFigure = (id: string): boolean => id in registry.figures;
