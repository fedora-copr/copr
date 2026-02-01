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
