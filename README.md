# nf-cmgg-test-datasets
Test datasets for unit tests with the nf-cmgg pipelines

## data/genomics/homo_sapiens/illumina/cram/SVcontrol
SVcontrol: subsetted crams for testing of nf-cmgg-structural
- nf-cmgg.SVcontrol.PosCon1.cram
    sample with a homozygous deletion upstream of CHST6 (hg38.chr16:75,500,000-75,538,999). Reads subsetted chr16:75,000,000-75,600,000. Sib of nf-cmgg.SVcontrol.PosCon2.cram.
- nf-cmgg.SVcontrol.PosCon2.cram
    sample with a homozygous deletion upstream of CHST6 (hg38.chr16:75,500,000-75,538,999). Reads subsetted chr16:75,000,000-75,600,000. Sib of nf-cmgg.SVcontrol.PosCon1.cram.
- nf-cmgg.SVcontrol.PosCon3.cram
    sample with a homozygous deletion in TTLL5 (hg38.chr14:75,771,149-75,772,647). Reads subsetted chr14:75,400,000-76,000,000.
- nf-cmgg.SVcontrol.PosCon4.cram
    sample with two heterozygous deletion on chrX with uncertain boundaries (hg38.chrX:154,097,604-154,154,739 and chrX:153,773,230-153,776,214). Reads subsetted chrX:153,400,000-154,000,000.
