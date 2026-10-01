-- Lab 01, step 3 - TRANSFORM
-- From nested carts to an answer: revenue per product category.

-- 1. one row per product in a cart (the cart's product list is "unnested")
--    a cart with 4 products becomes 4 rows; the cart's own columns repeat
CREATE OR REPLACE TABLE cart_items AS
SELECT
    c.id               AS cart_id,        -- which cart
    c.userId           AS user_id,        -- which customer
    item.id            AS product_id,     -- which product
    item.quantity      AS quantity,       -- how many pieces
    item.price         AS unit_price,     -- price of one piece
    item.total         AS amount,         -- quantity x price
    item.discountedTotal AS amount_paid   -- the amount after the discount
FROM raw_carts AS c, unnest(c.products) AS t(item);   -- item = one product of the cart

-- 2. join with products, aggregate per category
--    the cart item has no category, so we look it up in raw_products
CREATE OR REPLACE TABLE revenue_by_category AS
SELECT
    p.category,
    count(DISTINCT ci.cart_id)      AS carts,                   -- carts with this category
    sum(ci.quantity)                AS items_sold,              -- pieces sold
    round(sum(ci.amount), 2)        AS revenue,                 -- before the discount
    round(sum(ci.amount_paid), 2)   AS revenue_after_discount   -- what customers paid
FROM cart_items AS ci
JOIN raw_products AS p ON p.id = ci.product_id   -- match each item to its product
GROUP BY p.category                              -- one result row per category
ORDER BY revenue_after_discount DESC;            -- the biggest category first