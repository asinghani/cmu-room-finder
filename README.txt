CMU Room Finder

cmuroom get-cookie
cmuroom [--date DATE] update


Lists:
cmuroom categories

cmuroom [--favorite] [--require-full] [--filter KEYWORD] [--category CATEGORY] [--min-capacity CAPACITY] rooms


Room Info:
cmuroom [--verbose] [--date DATE] room ROOM


Available Lookups:
cmuroom [--favorite] [--require-full] [--verbose] [--date DATE] [--filter KEYWORD] [--category CATEGORY] [--min-capacity CAPACITY] available NUMBER_OF_HOURS - show all rooms available right now and continuing for the next NUMBER_OF_HOURS hours

cmuroom [--favorite] [--require-full] [--verbose] [--date DATE] [--filter KEYWORD] [--category CATEGORY] [--min-capacity CAPACITY] available-at START_TIME END_TIME - show all rooms which will be available from START_TIME to END_TIME

cmuroom [--favorite] [--require-full] [--verbose] [--date DATE] [--filter KEYWORD] [--category CATEGORY] [--min-capacity CAPACITY] available-soon WITHIN_HOURS - show all rooms which are not currently available, but will become available within WITHIN_HOURS

HOURS can be specified as integer, float, and optionally with "m"/"min" suffix for minutes instead

-D = --date
-F = --filter
-C = --category
-M = --min-capacity

-r = --require-full = only show those with 25Live info available
-f = --favorite = only show those that are favorited
-v = --verbose = show more data
