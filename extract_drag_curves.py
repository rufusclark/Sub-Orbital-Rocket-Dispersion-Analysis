import argparse
import csv
from pathlib import Path

MACH_HEADER = "Mach"
CD_Power_OFF_HEADER = "CD Power-Off"
CD_POWER_ON_HEADER = "CD Power-On"


def main():
    # setup argparse
    parser = argparse.ArgumentParser(
        description="Extract powerOnDragCurve and powerOffDragCurve from RASAero Aero Plots csv and write files to save directory"
    )
    parser.add_argument(
        "-i", "--input", help="Path to RASAeroII Aero Plot csv"
    )

    # extract args
    args = parser.parse_args()
    inpath = Path(args.input)

    # check input file exists
    if not inpath.exists():
        print(f"File {inpath.resolve()} does not exist")
        return

    # open input file
    dirpath = inpath.parent
    with open(inpath) as infile:
        reader = csv.DictReader(infile)

        # check csv headers exist
        fields = reader.fieldnames
        if (
            (MACH_HEADER not in fields) or
            (CD_POWER_ON_HEADER not in fields) or
            (CD_Power_OFF_HEADER not in fields)
        ):
            print(
                f"{inpath} is missing one of the following headers, {[MACH_HEADER, CD_POWER_ON_HEADER, CD_Power_OFF_HEADER]}"
            )
            return

        # read csv into memory
        rows = list(reader)

    # create two new files
    for header, outpath in zip([CD_POWER_ON_HEADER, CD_Power_OFF_HEADER], ["powerOnDragCurve.csv", "powerOffDragCurve.csv"]):

        # setup
        lastMach = 0

        # create output path
        outpath = dirpath / outpath

        # open out file
        with open(outpath, "w", newline="") as outfile:
            # setup writer
            writer = csv.DictWriter(
                outfile, fieldnames=[MACH_HEADER, header]
            )

            # write csv rows
            for row in rows:

                # skip if Mach number isn't increasing
                Mach = row[MACH_HEADER]
                if float(Mach) <= lastMach:
                    continue
                else:
                    lastMach = float(Mach)

                # write row to csv
                writer.writerow(
                    {
                        MACH_HEADER: Mach,
                        header: row[header]
                    }
                )

            print(
                f"Extracted '{MACH_HEADER}' and '{header}' to {outpath.resolve()}"
            )


if __name__ == "__main__":
    main()
