"""Exercise Slurm submission and per-node container setup without a cluster."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOCK_TOOL = '''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['TOOL_LOG'], 'a') as stream:
    stream.write(json.dumps({'tool': name, 'args': args}) + '\\n')
if name == 'sbatch':
    print('Submitted batch job 123')
elif name == 'srun':
    tasks = int(next(arg.split('=', 1)[1] for arg in args if arg.startswith('--ntasks=')))
    command = args[args.index('bash'):]
    for rank in range(tasks):
        result = subprocess.run(command, env=dict(os.environ, SLURM_PROCID=str(rank)))
        if result.returncode:
            sys.exit(result.returncode)
elif name in ('singularity', 'apptainer') and os.environ.get('FAIL_RANK'):
    if 'PANDORA_NODE_ID=' + os.environ['FAIL_RANK'] in args:
        sys.exit(7)
'''


class ClusterLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.image = self.root / 'image with spaces.sif'
        self.image.touch()
        for name in ('sbatch', 'srun', 'singularity', 'apptainer'):
            executable = self.root / name
            executable.write_text(MOCK_TOOL)
            executable.chmod(0o755)
        self.log = self.root / 'tools.jsonl'
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('SLURM_', 'PANDORA_'))}
        self.env.update(
            PATH=str(self.root) + ':' + os.environ['PATH'],
            TOOL_LOG=str(self.log), PANDORA_IMAGE=str(self.image),
            PANDORA_DATA_ROOT=str(self.root / 'scratch with spaces'),
            PANDORA_LOG_DIR=str(self.root / 'logs'),
            PANDORA_ACCOUNT='project_test',
        )
        self.args = ['main.py', '--config', 'config with spaces.json', 'rsa',
                     '--nodes', '3', '--nproc', '4', '--n', '64']

    def run_launcher(self, name='run_apptainer_lumi.sh', args=None):
        return subprocess.run(['bash', str(ROOT / name), *(self.args if args is None else args)],
                              env=self.env, text=True, capture_output=True)

    def calls(self, tool):
        return [entry['args'] for line in self.log.read_text().splitlines()
                if (entry := json.loads(line))['tool'] == tool]

    def test_batch_requests_nodes_and_workers_per_node(self):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        batch, = self.calls('sbatch')
        for option in ('--nodes=3', '--ntasks=3', '--ntasks-per-node=1', '--cpus-per-task=4'):
            self.assertIn(option, batch)
        self.assertEqual(batch[-len(self.args):], self.args)
        self.assertIn('Submitted batch job 123', result.stdout)

    def test_each_rank_gets_its_own_database_and_complete_arguments(self):
        for launcher, runtime in [('run_apptainer_lumi.sh', 'singularity'),
                                  ('run_apptainer_toubkal.sh', 'apptainer')]:
            with self.subTest(launcher=launcher):
                self.log.unlink(missing_ok=True)
                self.env.update(SLURM_JOB_ID='123', SLURM_JOB_NUM_NODES='3', SLURM_CPUS_PER_TASK='4')
                result = self.run_launcher(launcher)
                self.assertEqual(result.returncode, 0, result.stderr)
                step, = self.calls('srun')
                for option in ('--nodes=3', '--ntasks=3', '--ntasks-per-node=1',
                               '--cpus-per-task=4', '--kill-on-bad-exit=1'):
                    self.assertIn(option, step)
                containers = self.calls(runtime)
                self.assertEqual(len(containers), 3)
                directories = []
                for rank, command in enumerate(containers):
                    self.assertIn(f'PANDORA_NODE_ID={rank}', command)
                    self.assertIn('PANDORA_NODE_COUNT=3', command)
                    self.assertIn('PANDORA_WORKER_COUNT=4', command)
                    self.assertIn('/pandora/apptainer/run_node.sh', command)
                    self.assertEqual(command[-len(self.args):], self.args)
                    binding = next(arg for arg in command if arg.endswith(':/pandora-run'))
                    directory = Path(binding.rsplit(':', 1)[0])
                    self.assertEqual(directory.name, f'node-{rank}')
                    self.assertTrue((directory / 'pgdata').is_dir())
                    directories.append(directory)
                self.assertEqual(len(set(directories)), 3)
                self.assertFalse(self.calls('sbatch'))

    def test_bad_resources_fail_before_submission(self):
        for args in (['main.py', 'rsa', '--nodes', '0'],
                     ['main.py', 'rsa', '--nproc=-1'],
                     ['main.py', 'rsa', '--container_id', '0']):
            with self.subTest(args=args):
                self.assertNotEqual(self.run_launcher(args=args).returncode, 0)
        self.assertFalse(self.log.exists())

    def test_existing_allocation_must_fit_request(self):
        self.env.update(SLURM_JOB_ID='123', SLURM_JOB_NUM_NODES='2')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Allocation has 2 nodes', result.stderr)
        self.assertFalse(self.log.exists())

    def test_failure_in_one_node_fails_the_job(self):
        self.env.update(SLURM_JOB_ID='123', FAIL_RANK='1')
        self.assertEqual(self.run_launcher().returncode, 7)

    def test_equals_syntax_and_cpu_override(self):
        self.env['PANDORA_CPUS'] = '6'
        args = ['main.py', 'rsa', '--nodes=2', '--nproc=4']
        result = self.run_launcher(args=args)
        self.assertEqual(result.returncode, 0, result.stderr)
        batch, = self.calls('sbatch')
        self.assertIn('--nodes=2', batch)
        self.assertIn('--cpus-per-task=6', batch)
        self.assertEqual(batch[-len(args):], args)

    def test_large_job_selects_standard_partition(self):
        result = self.run_launcher(args=['main.py', 'rsa', '--nodes=5', '--nproc=4'])
        self.assertEqual(result.returncode, 0, result.stderr)
        batch, = self.calls('sbatch')
        self.assertIn('--partition=standard', batch)

    def test_spooled_batch_script_uses_original_repository(self):
        spooled = self.root / 'slurm_script'
        spooled.write_text((ROOT / 'run_apptainer_lumi.sh').read_text())
        self.env.update(SLURM_JOB_ID='123', PANDORA_REPO_DIR=str(ROOT))
        result = subprocess.run(['bash', str(spooled), *self.args],
                                env=self.env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        step, = self.calls('srun')
        self.assertIn(str(ROOT / 'apptainer/slurm_node.sh'), step)
        for container in self.calls('singularity'):
            self.assertIn(str(ROOT) + ':/pandora', container)


if __name__ == '__main__':
    unittest.main()
