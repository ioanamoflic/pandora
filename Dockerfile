FROM postgres

ADD sql_generate_table.sql /docker-entrypoint-initdb.d

RUN chmod a+r /docker-entrypoint-initdb.d

RUN apt-get update && \
    apt-get install -y git && \
    apt-get install -y pip 

RUN git clone https://github.com/ioanamoflic/pandora.git

RUN pip install -r pandora/requirements.txt
