Running Sanity Tests Against a PR
==================================

Simply open a PR and add a comment containing the `/packit test` command.  Our
CI/CD tooling will automatically build the RPMs, install them into a freshly
spawned VM in the Testing Farm, and execute the sanity tests.


Handling a Test Failure
-----------------------

Testing Farm does not allow easy SSH access to the machine that failed the
tests.  However, you can use a Fedora VM and mimic the environment preparation
using the playbook in this directory, and re-run the failing tests.

Follow these steps:

- **Prepare a Fedora VM** with an accessible IP address (e.g., `1.2.3.4`).  (See
  the `spawn-testing-machine` subdirectory for instructions on how to spawn one
  via EC2).

- **Ensure SSH access** to the `root` account: `ssh root@1.2.3.4`.

- **Create an inventory file**:

      $ cd ./prepare
      $ cat inventory
      [all]
      1.2.3.4

- **Run the preparation playbook**:

      $ PACKIT_PR_ID=4135 ansible-playbook ./machine-prepare.yml -i inventory

- **Re-run the tests**:

      $ ssh root@1.2.3.4
      # cd /tmp/copr_code/testing-farm
      # COPR_CLEANUP=false ./all-on-single-host.sh runtest-coprdir.sh  # one test
      # COPR_CLEANUP=false ./all-on-single-host.sh  # all tests


Flaky Tests
-----------

Some tests are known to be flaky, typically because they depend on an external
service we have no control over (e.g. the epel-7 builds downloading from
vault.centos.org).  Such tests are listed in the `FLAKY_TESTS` array in
`all-on-single-host.sh`; when one of them fails, the failure is reported in the
output (and in the final report) but it does not fail the overall test run.

When a flaky test fails, please re-run it manually (see above) before
investigating - it may simply pass this time.  If a flaky test starts to fail
repeatedly, fix the root cause and remove it from the `FLAKY_TESTS` list.
