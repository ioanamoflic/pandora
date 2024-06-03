# create ramdisk on mac (2 GB)
# shellcheck disable=SC2046
# shellcheck disable=SC2006
diskutil erasevolume HFS+ "RAMDisk" `hdiutil attach -nomount ram://4194304`
# change user to postgres, this will not work otherwise
sudo su postgres
mkdir /Volumes/RAMDisk/data
/Library/PostgreSQL/14/bin/initdb -D /Volumes/RAMDisk/data
/Library/PostgreSQL/14/bin/pg_ctl start -D /Volumes/RAMDisk/data
# check data dir is correct
psql -U postgres;
show data_directory;
