# Explore Demand draft

Updated October 22, 2026. Applies only to Explore Demand; the homepage and other pages retain their existing designs.

## Selection controls

Keep the introduction: “Every product has a story.” and “Follow how sales build, peak, and accumulate. Start with a pattern, then explore a history.”

Offer only “What keeps selling?” (Sustained Performer) and “What sells in a burst?” (Rapid Spike). Normal browsing uses histories that pass the dataset-boundary checks. Remove the All histories button and product search. Provide a Garment group dropdown and three clickable selected-example cards. Start with Swimwear to retain the existing introductory examples.

Example cards show names, actual smoothed sales previews, and days to 80% of observed sales. IDs remain internal and in Product details.

Choose up to three examples deterministically from each pattern/group: sort by days to 80% of sales, break ties by article ID, then select nearest rank to the 50th, 15th, and 85th percentiles. Prefer different product names; never repeat an article. These illustrate middle-paced, faster, and slower accumulation within the filtered group, not representative samples or manually reviewed exemplars. Preview curves use their own peak and history length, so their axes do not compare volume or duration. The day count supplies timing context. Show the selected count and full matching population.

“Show another example” cycles only these selected histories. A collapsed “Find another product” search retains access to all matching products, including an exact article-ID search. Require two characters and display up to six matches. Main charts and metrics continue to show any product selected through search or direct link.

Garment-group options are displayed alphabetically by label.

## Browsing category mapping

| Display label | Original garment groups |
| --- | --- |
| Jersey | Jersey Fancy; Jersey Basic |
| Underwear & Sleepwear | Under-, Nightwear; Socks and Tights |
| Accessories | Accessories |
| Blouses & Shirts | Blouses; Shirts |
| Knitwear | Knitwear |
| Dress | Dresses Ladies |
| Bottoms | Trousers; Trousers Denim; Skirts; Shorts |
| Swimwear | Swimwear |
| Shoes | Shoes |

These are draft browsing labels, not reclassifications of individual product types. In particular, the original Trousers and Trousers Denim groups contain some non-bottom products. The mapping follows the requested whole-group merges. It does not rewrite source metadata or change category statistics elsewhere.

Outdoor, Unknown, Dressed, Special Offers, Dresses/Skirts girls, and Woven/Jersey/Knitted mix Baby are outside these nine browsing categories. Their records are retained in the dataset.

Existing direct article links still open the requested history, even if it falls outside a normal pattern or category selection. Choosing a pattern, garment group, or different product resumes normal filtering. Such linked histories retain the existing boundary qualification when applicable.

Charts, key facts, product details, comparison links, and optional technical details otherwise remain unchanged. Category definitions live in src/explore-groups.js.

## Main-chart inspection

Explore Demand enables pointer inspection on both main chart views. The nearest observed date drives a vertical guide, visible series markers, and a readout. Sales view reports MA7 units/day and raw daily units even when the daily line is hidden. Accumulated view reports cumulative observed units and share. Values use actual exported/reconstructed rows; no interpolated sales are invented.

Touch users can tap/drag; the readout moves below the chart on small screens. Focus the chart and use arrow keys, Home, or End to inspect dates; Escape dismisses the readout. Other pages retain their existing chart interaction behavior.

The technical section omits the duplicate product heading, metadata/story, and summary metric boxes. Additional summary values, including strongest 7-day share, remain under More product measures. Daily CSV export is a small underlined text action; it generates a CSV locally for the displayed date range.

The outer “Look closer at the data” dropdown and introductory sentence have been removed. More product measures is the sole summary dropdown; the remaining detailed charts and data controls follow directly.

All technical content—additional measures, peak definitions, date controls, chart tabs, daily rows, and CSV download—is contained inside the single collapsed-by-default More product measures dropdown.
