"""
BuildDispatcher related classes.
"""

from copr_common.worker_manager import GroupWorkerLimit
from copr_backend.dispatcher import BackendDispatcher
from copr_backend.rpm_builds import (
    ArchitectureWorkerLimit,
    BuildTagLimit,
    RPMBuildWorkerManager,
    BuildQueueTask,
)
from ..exceptions import FrontendClientException


class _PriorityCounter:
    def __init__(self):
        self._counter = {}

    def get_priority(self, task):
        """
        Calculate the "dynamic" task priority, based on the actual queue size
        and queue structure.  We have this matrix of counters:

            _counter["background"]["user"]["arch"]["sandbox"] = value

        Each dimension "re-sets" the priority and starts counting from zero.
        Simply, the later the task is submitted (higher build ID) the less
        priority it gets (== gets higher priority number).

        We want to have separate counters for:

        - normal and background builds (background jobs are always penalized by
          the BuildQueueTask.frontend_priority), those are two separate but
          equivalent queues here

        - for each architecture (includes the source builds), that's because
          each architecture needs to have it's own "queue"/pool of builders
          (doesn't make sense to penalize e.g. ppc64le tasks and delay them
          because of a heavy x86_64 queue)

        - For each sandbox.  Each sandbox is equivalent to each other.  This
          means that builds submitted to 'jdoe/foo--user1' should be taken with
          the same priority as 'jdoe/baz-user1' (note the same owner pattern!)
          no matter *when* they are submitted.  This is useful when 'jdoe/foo'
          get's huge batch of builds, and _then_ after some time some _other_
          builds are submitted into the 'jdoe/baz'; those 'jdoe/baz builds could
          be blocked for a very long time.  See below.

        Note that for large queues, build_dispatcher isn't sometimes able to
        handle all the tasks in the priority queue in one cycle (we are able to
        process several hundreds, or at most thousands of tasks — depending on
        the 'sleeptime' value).  Therefore, the priority really matters here, as
        we want to avoid all kinds of the weird builder/queue starving
        situations.  In other words — if task isn't processed in one
        WorkerManager.run(timeout=???) cycle — it may stay "pending" for many
        other cycles too (depending on how quickly the overall queue get's
        processed).
        """

        def _get_subdict(source, arg):
            source.setdefault(arg, {})
            return source[arg]

        background = _get_subdict(self._counter, task.background)
        owner = _get_subdict(background, task.owner)
        arch = _get_subdict(owner, task.requested_arch or "srpm")

        # calculate from zero
        arch.setdefault(task.sandbox, 0)
        arch[task.sandbox] += 1
        return arch[task.sandbox]


class BuildDispatcher(BackendDispatcher):
    """
    Kick-off build dispatcher daemon.
    """
    task_type = 'build'
    worker_manager_class = RPMBuildWorkerManager

    def __init__(self, backend_opts):
        super().__init__(backend_opts)
        self.max_workers = backend_opts.builds_max_workers

        for tag_type in ["arch", "tag"]:
            lclass = ArchitectureWorkerLimit if tag_type == "arch" else \
                     BuildTagLimit
            for tag, limit in backend_opts.builds_limits[tag_type].items():
                self.log.info("setting %s(%s) limit to %s", tag_type, tag, limit)
                self.limits.append(lclass(tag, limit))

        for limit_type in ['sandbox', 'owner']:
            max_builders = backend_opts.builds_limits[limit_type]
            self.log.info("setting %s limit to %s", limit_type, max_builders)
            self.limits.append(GroupWorkerLimit(
                lambda x, limit=limit_type: getattr(x, limit),
                max_builders,
                name=limit_type,
            ))

    def get_frontend_tasks(self):
        """
        Retrieve a list of build jobs to be done.
        """
        try:
            raw_tasks = self.frontend_client.get('pending-jobs').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception("Retrieving build jobs from %s failed with error: %s",
                               self.opts.frontend_base_url, error)
            return []

        tasks = []
        priority = _PriorityCounter()
        for raw in raw_tasks:
            task = BuildQueueTask(raw)
            task.backend_priority = priority.get_priority(task)
            tasks.append(task)
        return tasks

    def get_cancel_requests_ids(self):
        try:
            return self.frontend_client.get('build-tasks/cancel-requests').json()
        except (FrontendClientException, ValueError) as error:
            self.log.exception("Retrieving build jobs from %s failed with error: %s",
                               self.opts.frontend_base_url, error)
            return []

    def report_canceled_task_id(self, task_id, was_running):
        self.frontend_client.post('build-tasks/canceled/{}'.format(task_id),
                                  data=None if not was_running else was_running)
