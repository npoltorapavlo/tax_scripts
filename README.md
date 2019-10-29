#### SYNOPSIS
```
python tax.py <command> [<args>]
```

#### DESCRIPTION
a tax tool for https://cabinet.tax.gov.ua/ . uses a database and prints reports

#### COMMANDS
    add <YYYY-MM-DD> <CUR> <amount> <tax>
        Add an income.
    remove <id>
        Remove an income.
    print
        Print report for all saved periods.