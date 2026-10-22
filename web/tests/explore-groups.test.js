import test from 'node:test';
import assert from 'node:assert/strict';
import { EXPLORE_GROUPS, exploreGroupFor, matchesExploreGroup } from '../src/explore-groups.js';

test('draft browsing groups assign each source once and preserve requested merges', () => {
  assert.equal(EXPLORE_GROUPS.length, 9);
  const sources = EXPLORE_GROUPS.flatMap(g => g.sources);
  assert.equal(new Set(sources).size, sources.length);
  for (const source of ['Jersey Basic', 'Jersey Fancy']) assert.equal(exploreGroupFor(source), 'Jersey');
  for (const source of ['Trousers', 'Trousers Denim', 'Skirts', 'Shorts']) assert.ok(matchesExploreGroup({garment_group_name:source}, 'Bottoms'));
  assert.equal(exploreGroupFor('Shirts'), 'Blouses & Shirts');
  assert.equal(exploreGroupFor('Socks and Tights'), 'Underwear & Sleepwear');
  assert.equal(exploreGroupFor('Outdoor'), undefined);
  assert.equal(matchesExploreGroup({garment_group_name:'Unknown'}, 'Jersey'), false);
});
