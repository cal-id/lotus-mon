
# ------------------------------- SETTINGS ------------------------------------

# the top directory where to serve from
# (actually everything is saved under <PATH_TO_SAVE><MIDDLE><more...>)
# the <more...> is documented under the database models script
PATH_TO_SAVE = "/var/www/html/"

# the base url to serve the page
HOST_ADDRESS = "lotus-mon.jc.rl.ac.uk"

# the additional section of the url for serving media
# so all files will be saved at <PATH_TO_SAVE><MIDDLE><more file path...>
#         ... will be hosted at <BASE_URL><MIDDLE><more file path...>
MIDDLE = "/saves/"
assert MIDDLE[0] == "/" and MIDDLE[-1] == "/"

# the root of ganglia (ends in '/graph.php?') the ? is important
GANGLIA_ROOT = "http://mgmt.jc.rl.ac.uk/ganglia/graph.php?"
assert GANGLIA_ROOT[-1] == "?"

# a list of lsf fields to use
# possibilities:
# ["jobid", "stat", "user", "queue", "job_description", "job_name",
#  "proj_name", "application", "service_class", "job_group", "job_priority",
#  "dependency", "command", "pre_exec_command", "post_exec_command",
#  "resize_notification_command", "pids", "exit_code", "exit_reason",
#  "from_host", "first_host", "exec_host", "nexec_host", "submit_time",
#  "start_time", "estimated_start_time", "specified_start_time",
#  "specified_terminate_time", "time_left", "finish_time", "%complete",
#  "warning_action", "action_warning_time", "cpu_used", "run_time",
#  "idle_factor", "exception_status", "slots", "mem", "max_mem", "avg_mem",
#  "memlimit", "swap", "swaplimit", "min_req_proc", "max_req_proc",
#  "effective_resreq", "network_req", "filelimit", "corelimit", "stacklimit",
#  "processlimit", "input_file", "output_file", "error_file", "output_dir",
#  "sub_cwd", "exec_home", "exec_cwd", "forward_cluster", "forward_time"]
LSF_FIELDS = ["jobid", "stat", "user", "queue", "job_description", "job_name",
              "proj_name", "application", "service_class", "job_group",
              "job_priority", "dependency", "command", "pre_exec_command",
              "post_exec_command", "resize_notification_command", "pids",
              "exit_code", "exit_reason", "from_host", "first_host",
              "exec_host", "nexec_host", "submit_time", "start_time",
              "estimated_start_time", "specified_start_time",
              "specified_terminate_time", "time_left", "finish_time",
              "%complete", "warning_action", "action_warning_time",
              "cpu_used", "run_time", "idle_factor", "exception_status",
              "slots", "mem", "max_mem", "avg_mem", "memlimit", "swap",
              "swaplimit", "min_req_proc", "max_req_proc", "effective_resreq",
              "network_req", "filelimit", "corelimit", "stacklimit",
              "processlimit", "input_file", "output_file", "error_file",
              "output_dir", "sub_cwd", "exec_home", "exec_cwd",
              "forward_cluster", "forward_time"]

# define the column numbers of interesting columns
LSF_FIELDS_INDEX_USER = LSF_FIELDS.index("user")
LSF_FIELDS_INDEX_COMMAND = LSF_FIELDS.index("command")
LSF_FIELDS_INDEX_QUEUE = LSF_FIELDS.index("queue")

# Note: From now on ensure that the default values aren't changed:
#         - The database model needs updating if the default values change.
#         - Search for 'django makemigrations' for how to do this

###

# define the time periods ganglia can accept
# possibilities:                                            DO NOT CHANGE THESE
GANGLIA_TIMES_DEFAULT = ["hour", "2hr", "4hr", "8hr", "12hr", "day", "3day",
                         "week", "2week", "3week", "month", "2month", "4month",
                         "8month", "year", "2year", "3year"]
# ones to actually save                                            CHANGE THESE
GANGLIA_TIMES = ["hour", "2hr", "4hr"]

###

# define the values for report plots of a host
# possibilities:                                            DO NOT CHANGE THESE
GANGLIA_REPORTS_DEFAULT = ["load_report", "mem_report", "cpu_report",
                           "network_report"]
# ones to actually save                                            CHANGE THESE
GANGLIA_REPORTS = ["load_report", "mem_report", "cpu_report",
                   "network_report"]

###

# define the values for the basic plots
# possibilities:                                            DO NOT CHANGE THESE
GANGLIA_BASIC_DEFAULT = ['pkts_in', 'mem_free', 'NTPD-OFFSET', 'disk_total',
                         'pkts_out', 'cpu_user', 'cpu_wio', 'part_max_used',
                         'proc_run', 'cpu_idle', 'load_fifteen', 'cpu_nice',
                         'mem_shared', 'load_one', 'mem_buffers', 'disk_free',
                         'swap_free', 'cpu_aidle', 'bytes_in', 'bytes_out',
                         'cpu_system', 'mem_cached', 'proc_total', 'load_five']
# ones to actually save                                            CHANGE THESE
GANGLIA_BASIC = []
