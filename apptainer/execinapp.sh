pg_ctl init
echo 'host all all 0.0.0.0/0 trust'>> /var/lib/postgresql/data/pg_hba.conf

pg_ctl start

export PYTHONPATH=$PYTHONPATH:/pandora

cd /pandora

#python3 benchmarking/benchmark_db.py
python3 main.py