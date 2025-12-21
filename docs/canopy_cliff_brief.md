# City of Melbourne Urban Forest: Canopy Cliff Brief

**For:** Capital works and urban forest asset planning
**Scope:** 82,036 council trees across 17 precincts. Life expectancy data from the tree register, heat vulnerability from the 2018 Victorian Heat Vulnerability Index.
**Every figure below is traceable to** `outputs/tables/` **and the charts in** `outputs/figures/`.

## Findings

**1. The city-wide cliff arrives in years 21 to 40, not in the near term.**
Reactive renewal needs about $0.7M a year in years 11 to 20. It then jumps to $3.6M a year in years 21 to 30. Of the $90.1M scheduled replacement cost, 65 percent ($58.3M) falls in years 21 to 40, driven by 37,099 trees in those two bands. *(Q1)*

**2. A levelled budget of $1.65M a year, starting now, avoids the spike.**
That is the smallest constant annual budget whose cumulative spend never falls behind cumulative need. It works by renewing some trees before end of life, which replaces canopy progressively instead of in one wave. It is less than half the reactive peak. *(Q1)*

**3. Kensington, Carlton and Carlton North are the priority precincts.**

| Rank | Precinct | Cliff index | Near-term trees | Near-term cost | Average HVI |
|---|---|---|---|---|---|
| 1 | Kensington | 79.5 | 639 (8.5%) | $939k | 1.85 |
| 2 | Carlton | 74.4 | 285 (6.5%) | $653k | 2.71 |
| 3 | Carlton North | 69.2 | 233 (10.0%) | $585k | 1.01 |
| 4 | North Melbourne | 61.5 | 246 (5.2%) | $429k | 2.70 |
| 5 | South Yarra | 56.4 | 228 (8.7%) | $493k | 1.01 |

- The index gives equal weight to three parts: near-term cost per hectare, near-term share of trees, and heat vulnerability. *(Q2)*
- **Kensington** ranks first or second in all eight sensitivity scenarios. *(Q8)*
- **Carlton North** scores on cost density and near-term share, **not heat**. Its average HVI of 1.01 is among the lowest in the city. *(Q2, Q4)*

**4. Carlton, North Melbourne and Kensington are where canopy loss and heat vulnerability coincide.**
These are the only ranked precincts above the median on both heat vulnerability and near-term cost per hectare. Carlton and North Melbourne have the highest heat scores in the study area (2.7). They should come first in any heat-led planting programme. *(Q4)*

**5. 111 micro-cliffs pinpoint where crews should start.**
- These are DBSCAN clusters of at least five near-term trees within 15 m of each other. They contain 1,600 of the 4,945 near-term trees.
- The largest are single-genus park plantings, mostly eucalypts and acacias in Royal Park (Parkville). A Myoporum block of 53 trees in Kensington is the costliest single cluster ($148k).
- Coordinates for each cluster are in `micro_cliffs_near_term.csv`. *(Q5)*

**6. Two genera dominate the near-term liability.**
Eucalyptus (25 percent) and Ulmus (15 percent) make up 40 percent of near-term trees. Ulmus is the costliest genus ($2.2M), because the elms are large, mature avenue trees. Replacing either genus with a single species would recreate the same-age risk. *(Q6)*

## Recommendation

1. Adopt a levelled renewal budget of about **$1.65M a year**. Front-load it to Kensington, Carlton and Carlton North, rather than waiting for the reactive peak in years 21 to 30.
2. Within those precincts, programme works by micro-cliff, starting with the largest clusters. Stagger replacement inside each cluster over several years so canopy is never lost all at once.
3. Diversify the species used to replace Eucalyptus and Ulmus stands.
4. **Close the assessment gap first in Parkville.** It holds $8.9M of the $15.8M liability that cannot be scheduled, because 34 percent of its trees have no life expectancy assessment. *(Q7)*

## Watch list (not ranked, fewer than 100 trees)

Princes Hill (65 trees) has the highest near-term share in the city: 14 percent, or 9 trees. It is too small to rank reliably, but it warrants inspection. Central City (26 trees) and Fishermans Bend (61 trees) have no near-term trees.

## Assumptions and limitations

- **Replacement costs are analyst assumptions**, set by trunk diameter from $400 to $6,000 per tree. They are not council procurement rates, so read dollar figures as directional. Cost scenarios in Q8 show the ranking at the top is robust to this.
- **55 percent of trunk diameters are imputed** from the median of the same genus and age class. The share is higher for older trees.
- **21 percent of trees (17,407) have no life expectancy assessment.** Their $15.8M cost is excluded from the timeline, so the true liability is higher than shown.
- **Timeline years are counted from the assessment date**, which Council notes is dated. They are not calendar years.
- **Precinct areas are convex hulls of tree locations**, because no official boundaries are published. Per-hectare figures are therefore indicative.
- **The HVI is from 2018 and ranks SA1s across all of metropolitan Melbourne.** Inner Melbourne scores sit between 1 and 3, so heat enters the index as a percentile rank across these precincts.
- **Excluded:** 28 trees tagged Richmond, Brunswick or Brunswick West, because they belong to neighbouring councils.
