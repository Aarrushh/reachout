# product.md  (Layer 3: what ReachOut is)

ReachOut is a hyperlocal demand router. It flips the normal shopping app.

In a normal app you browse a store's catalogue. In ReachOut you say what you
need, and nearby shops that have it respond.

## The flow

1. A shopper searches for any item.
2. The system looks at shops within a radius, 5 km by default.
3. It checks each shop's live inventory for a match.
4. Every matched shop is pinged instantly. The shopper sees who has it,
   how far, at what price, and how much is in stock.
5. The shopper goes to the shop or asks for delivery.

## The two sides

Retailer side: a shop's inventory is synced live. Every sale, restock, and
new item updates the shared store in near real time. In this MVP the
`inventory_simulator.py` stands in for that live feed.

Consumer side: a search experience that feels like a quick-commerce app but
is powered by many local shops rather than one warehouse.

## Where the value is

Not in the AI. The AI is a thin layer. The value is in inventory accuracy,
fast shop response, and a frictionless handoff to pickup or delivery. If
the stock data is stale, the whole thing breaks. So the MVP starts narrow:
one city, a few categories, a handful of shops.

## MVP scope

One city (Mumbai in the sample data). Four categories: pharmacy, grocery,
electronics, stationery. Eight sample shops. Live inventory simulation.
Search, radius filter, instant ping, ranked results.
