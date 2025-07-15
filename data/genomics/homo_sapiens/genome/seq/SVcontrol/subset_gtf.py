GTF_FILE = '/home/nvnieuwk/Documents/ugents3/reference-data/genomes/Hsapiens/GRCh38/seq/gencode.v48.basic.annotation.gtf'
OUTPUT_FILE = '/home/nvnieuwk/Documents/nf-cmgg/test-datasets/data/genomics/homo_sapiens/genome/seq/SVcontrol/reference.gtf'

REGIONS = {
    'chr16': [949851, 1608957],
    'chr14': [294403, 1014143],
    'chrX': [396962, 1014377]
}

def main():
    out_gtf = open(OUTPUT_FILE, "w")
    with open(GTF_FILE, "r") as gtf:
        line = gtf.readline()
        while line != "":
            if line.startswith("#"):
                out_gtf.write(line)
            else:
                split_line = line.split("\t")
                chr = split_line[0]
                if chr in REGIONS.keys():
                    region = REGIONS[chr]
                    start = int(split_line[3])
                    stop = int(split_line[4])
                    if start > region[0] and stop < region[1]:
                        out_gtf.write(line)
            line = gtf.readline()

if __name__ == "__main__":
    main()