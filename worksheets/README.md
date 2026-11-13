# Worksheets for teachers

`index.html` is a single page that makes free PISA-style maths worksheets, a teacher's key that explains every wrong answer, and a class report that says what to reteach first. From the report it makes a follow-up set on the same mistakes with new numbers, and once the class has sat it, it compares the two rounds. It needs no installation and no internet once saved, and nothing typed into it leaves the device. It works in English and Hindi: the switch at the top changes every word on the page, and the same set number gives the same questions, numbers and answer letters in both.

- Use it online: https://manik-maurya.github.io/Confusion-Mapper/worksheets/
- Or download `index.html` and open it in any browser.
- The guide for teachers is in [`../docs/pisa-teacher-guide.md`](../docs/pisa-teacher-guide.md).

The questions are not written in this page. It carries a fixed pool of 200 units in English and the same 200 in Hindi, built by `confusion_mapper/pisa.py`, so the Python templates remain the only place an answer is worked out. After changing a template, rebuild the pool:

```bash
python worksheets/build_pool.py
```

`tests/test_worksheets.py` fails if the pool in the page drifts from the generator, and it runs the page's own scoring code in Node against the Python scoring on random classes, in both languages. To click through the whole page the way a teacher would, in English and then in Hindi, install jsdom (`npm install jsdom`) and run `node worksheets/check_page.js`.
