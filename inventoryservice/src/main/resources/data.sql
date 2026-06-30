-- Seed data for load testing (Gatling, Phase 8) and chaos experiments (Phase 10).
--
-- ddl-auto is create-drop, so this runs against a freshly created schema on every
-- application startup (spring.jpa.defer-datasource-initialization=true ensures Hibernate
-- creates the tables first; spring.sql.init.mode=always makes Spring Boot run this file
-- against the Postgres datasource instead of skipping it, which is the default for
-- non-embedded databases).
--
-- Quantity is set high (1,000,000) so a full 50-user / 5.5-minute Gatling trial — or many
-- repeated trials across the 320-trial experiment matrix — won't run out of stock and
-- introduce stock-exhaustion failures that would be mistaken for chaos-induced failures.

INSERT INTO inventory_items (id, sku, name, price, quantity, status, version) VALUES
  ('a1b2c3d4-0000-4000-8000-000000000001', 'SKU-001', 'Gatling Load Test Item', 99.99, 1000000, 'IN_STOCK', 0);
