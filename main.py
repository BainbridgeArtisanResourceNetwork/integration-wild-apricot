"""
FIXME: HELP DOCSTRING
"""
import sys
import getopt
import datetime
import logging
import pytz
import re

from dateutil.parser import parse
from os import listdir
from os.path import isfile, join

import integrations.wildapricot.api as waApi

data_path = './data'


def configure_logger():
    # create logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)


def main():
    """
    """
    configure_logger()

    # FIXME
    apiKey = ""

    old_data_filename = None
    new_data_filename = None

    # parse command line options
    try:
        opts, _ = getopt.getopt(sys.argv[1:], "h", ["help", "old-data=", "new-data="])
    except getopt.error as err:
        print(err)
        print("for help use --help")
        sys.exit(2)
    # process options
    for opt, v in opts:
        if opt in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif opt == "--old-data":
            old_data_filename = v
        elif opt == "--new-data":
            new_data_filename = v

    utc = pytz.utc
    now = datetime.datetime.now(utc)

    if (not old_data_filename and new_data_filename) or (old_data_filename and not new_data_filename):
        logging.error("Need both --old-data and --new-data, or neither")
        sys.exit(1)

    if not old_data_filename:
        # Load most recent data file to compare against
        file_pattern = re.compile(r'^\d{12}\.pickle$')
        data_filenames = [join(data_path, f) for f in listdir(data_path) if file_pattern.match(f) and isfile(join(data_path, f))]
        data_filenames.sort(reverse=True)  # Most recent first
        old_data_filename = data_filenames[0]
    old_events = waApi.WaApiClient.load_data_from_file(old_data_filename)

    if not new_data_filename:
        # Load events from WildApricot and save into new data file
        api = waApi.WaApiClient(None, None)
        api.authenticate_with_apikey(apiKey, "events_view")
        new_events = api.get_events()

        timestamp = now.strftime("%Y%m%d%H%M")
        data_file = "./data/{}.pickle".format(timestamp)
        waApi.WaApiClient.dump_data_to_file(data_file, new_events)
    else:
        new_events = waApi.WaApiClient.load_data_from_file(new_data_filename)

    def filter_by_tag(e, t):
        filtered_events = [x for x in e if t in x.Tags]
        filtered_events_by_id = {}
        for event in filtered_events:
            start_date = parse(event.StartDate)
            if start_date > now:
                filtered_events_by_id[event.Id] = event
        return filtered_events_by_id

    # Keyed by event id
    old_by_tag = filter_by_tag(old_events, 'eta-class')
    new_by_tag = filter_by_tag(new_events, 'eta-class')

    report = list()
    for event_id in new_by_tag.keys():
        event = new_by_tag[event_id]
        if event_id not in old_by_tag:
            event.report_type = 'NEW'
            report.append(event)
        else:
            old_event = old_by_tag[event_id]
            new_confirmed_count = event.ConfirmedRegistrationsCount
            old_confirmed_count = old_event.ConfirmedRegistrationsCount
            if new_confirmed_count != old_confirmed_count:
                event.report_type = 'UPDATE'
                report.append(event)

    for event in report:
        start_date = parse(event.StartDate)
        end_date = parse(event.EndDate)
        confirmed_count = event.ConfirmedRegistrationsCount
        print("==========================")
        print("Name: " + event.Name)
        print("TYPE: " + event.report_type)
        print("ID: " + str(event.Id))
        print("StartDate: " + str(start_date))
        print("EndDate: " + str(end_date))
        print("Attendees: {}/{} ({} pending)".format(confirmed_count,
                                                     event.RegistrationsLimit,
                                                     event.PendingRegistrationsCount))


if __name__ == "__main__":
    main()
