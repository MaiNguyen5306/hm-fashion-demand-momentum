// Browsing labels only: retain original dataset groups for analysis and details.
export const EXPLORE_GROUPS = [
  { label: 'Jersey', sources: ['Jersey Fancy', 'Jersey Basic'] },
  { label: 'Underwear & Sleepwear', sources: ['Under-, Nightwear', 'Socks and Tights'] },
  { label: 'Accessories', sources: ['Accessories'] },
  { label: 'Blouses & Shirts', sources: ['Blouses', 'Shirts'] },
  { label: 'Knitwear', sources: ['Knitwear'] },
  { label: 'Dress', sources: ['Dresses Ladies'] },
  { label: 'Bottoms', sources: ['Trousers', 'Trousers Denim', 'Skirts', 'Shorts'] },
  { label: 'Swimwear', sources: ['Swimwear'] },
  { label: 'Shoes', sources: ['Shoes'] },
].sort((a, b) => a.label.localeCompare(b.label, 'en'));
export const exploreGroupFor = source => EXPLORE_GROUPS.find(group => group.sources.includes(source))?.label;
export const matchesExploreGroup = (product, label) => EXPLORE_GROUPS.find(group => group.label === label)?.sources.includes(product.garment_group_name) ?? false;
