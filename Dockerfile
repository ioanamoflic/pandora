FROM postgres

ADD sql_generate_table.sql /docker-entrypoint-initdb.d

RUN chmod a+r /docker-entrypoint-initdb.d
