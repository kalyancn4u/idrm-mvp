-- DESTRUCTIVE — drops every IDRM object.
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO idrm_user;
GRANT ALL ON SCHEMA public TO public;
