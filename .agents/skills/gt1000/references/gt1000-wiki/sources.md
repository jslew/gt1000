# Sources

Use current official BOSS/Roland documentation for GT-1000 v4+ work.

## Official Manuals

| Document | Current file used for this extraction | URL |
|---|---|---|
| Owner's Manual | `GT-1000_eng08_W.pdf` | https://static.roland.com/assets/media/pdf/GT-1000_eng08_W.pdf |
| Parameter Guide | `GT-1000_parameter_eng13_W.pdf` | https://static.roland.com/assets/media/pdf/GT-1000_parameter_eng13_W.pdf |
| Sound List | `GT-1000_sound_eng05_W.pdf` | https://static.roland.com/assets/media/pdf/GT-1000_sound_eng05_W.pdf |
| MIDI Implementation | `GT-1000-MIDI-Implementation.pdf` | https://static.roland.com/assets/media/pdf/GT-1000-MIDI-Implementation.pdf |

Official support index:

https://www.boss.info/global/support/by_product/gt-1000/owners_manuals/

## Refresh Process

The PDFs are not committed. To refresh scratch copies:

```sh
scripts/fetch-current-manuals.sh /tmp/gt1000-manuals
```

Then inspect the extracted text:

```sh
rg -n "CONTROL ASSIGN|ASSIGN SETTING|AIRD PREAMP|MIDI SETTING|PatchCommon" /tmp/gt1000-manuals/*.txt
```

When extracting into this wiki, paraphrase and summarize. Do not paste large manual sections.
