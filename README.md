# nf-cmgg-test-datasets
Test datasets for unit tests with the nf-cmgg pipelines

## data/genomics/homo_sapiens/illumina/cram/SVcontrol
SVcontrol: subsetted crams for testing of nf-cmgg-structural
- testSV.PosCon1.cram
    sample with a homozygous deletion upstream of CHST6 (hg38.chr16:75,500,000-75,538,999). Reads subsetted chr16:75,000,000-75,600,000. Sib of PosCon2.cram.
- testSV.PosCon2.cram
    sample with a homozygous deletion upstream of CHST6 (hg38.chr16:75,500,000-75,538,999). Reads subsetted chr16:75,000,000-75,600,000. Sib of PosCon1.cram.
- testSV.PosCon3.cram
    sample with a homozygous deletion in TTLL5 (hg38.chr14:75,771,149-75,772,647). Reads subsetted chr14:75,400,000-76,000,000.
- testSV.PosCon4.cram
    sample with two heterozygous deletion on chrX with uncertain boundaries (hg38.chrX:154,097,604-154,154,739 and chrX:153,773,230-153,776,214). Reads subsetted chrX:153,400,000-154,000,000.

## data/genomics/homo_sapiens/illumina/bed/SVcontrol
SVcontrol: region of interest bed for testing of nf-cmgg-structural
- testSV.PosCon1and2.roi.bed
    bed file for chr16:74,949,851-75,608,957 with Ensembl Transcript IDs. 
- testSV.PosCon3.roi.bed
    bed file for chr14:75,294,403-76,014,143 with Ensembl Transcript IDs. 
- testSV.PosCon4.roi.bed
    bed file for chrX:153,396,962-154,014,377 with Ensembl Transcript IDs.

## data/genomics/homo_sapiens/illumina/cram
Commands used to create cram files
- samtools faidx chr2.fa
- bwa index chr2.fa
- samtools faidx chr2.fa chr2:47411000-47419000 > region.fa
- wgsim -N 10000 -1 100 -2 100 -r 0 -R 0 -X 0 region.fa sim1.fq sim2.fq
- bwa mem chr2.fa sim1.fq sim2.fq > sim.sam
- samtools view -bS sim.sam | samtools sort -o sim.sorted.bam
- samtools index sim.sorted.bam
- Create VAR file: chr2 47414421 47414421 0.5 T
- addsnv.py -v substitutie.var -f sim.sorted.bam -r chr2.fa -o bam_with_snv.bam -s 0.5 --force --picardjar picard.jar
- samtools sort -o bam_with_snv.sorted.bam bam_with_snv.bam
- samtools view -C -T chr2.fa -o bam_with_snv.sorted.cram bam_with_snv.sorted.bam
- samtools index bam_with_snv.sorted.cram
checking mutation in bam file: 
- samtools index bam_with_snv.sorted.bam
- samtools mpileup -f chr2.fa bam_with_snv.sorted.bam | grep 47414421
