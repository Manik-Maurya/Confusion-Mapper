# Maths in real life: a guide for teachers

These are free maths worksheets in the style of PISA, the international test that asks children to use maths in real situations instead of only doing sums. The situations are ones Indian children know: a phone data plan, the monsoon, the price of dal, the bus to the district headquarters, a school garden, a water tank on the roof.

What makes them different from other worksheets is the teacher's key. When a child gets a question wrong, the key does not only say "wrong". It says what the child probably believes. Did they add the percentage as if it were rupees? Find the area when the question asked for the fence? Think that a 20% rise and a 20% fall cancel out? Once you know which of these your class believes, you know what to teach on Monday.

You do not need to install anything, make an account, or be online. Nothing you type is sent anywhere.

## What you need

A phone or computer with a web browser, and a printer, or a photocopy shop nearby. Open the worksheets page:

- Online: https://manik-maurya.github.io/Confusion-Mapper/worksheets/
- Offline: save the page once (Ctrl+S on a computer, or Share and then Save on a phone) and open the saved file any time. You can forward the saved file to other teachers on WhatsApp.

## In Hindi

Press **हिन्दी** at the top of the page. The booklet, the teacher's key, the answer page and the class report all switch to Hindi. Anything you have already typed stays where it is.

The same set number gives the same questions in both languages, with the same numbers and the same answer letters. So if some children in your class read Hindi and some read English, print each child the booklet they are comfortable with and enter everyone's answers on one sheet. The report comes out in whichever language the page is in.

The Hindi is a first draft. A Hindi-medium maths teacher has not checked it yet, and the page says so. If a word sounds wrong, or too bookish for your children, please tell us. The file [`hindi-review.md`](hindi-review.md) has every sentence next to its English, with space for a better version.

हिन्दी में पढ़ाने वाले शिक्षकों के लिए: पेज के ऊपर "हिन्दी" दबाइए। पुस्तिका, कुंजी, उत्तर दर्ज करने का पेज और कक्षा रिपोर्ट, सब हिन्दी में आ जाएँगे। एक ही सेट नंबर से हिन्दी और अंग्रेजी में वही प्रश्न, वही संख्याएँ और वही उत्तर-अक्षर मिलते हैं, इसलिए एक ही उत्तर-पत्रक दोनों के लिए चलता है। हिन्दी अनुवाद अभी प्रारूप है। कोई शब्द अटपटा लगे तो जरूर बताइए।

## Six steps

**1. Make a set.** Choose how many units. A unit is one situation with three questions, about ten minutes. Four units suit one 40-minute period. Tick topics or situations if you want only some, or leave them all unticked for a mix. Press "Make worksheets". The page shows a set number, for example "Set 4821". Write it down. The same number always gives the same worksheets, so another teacher can use exactly your set.

**2. Print the student booklet.** Open "Student booklet" and press "Print". Each child needs one copy. If you cannot print, you can write one unit at a time on the board.

**3. Give the test.** About ten minutes per unit. Children write their answers on the booklet. The numbers are chosen so the working can be done by hand.

**4. Mark with the teacher's key.** Print or open "Teacher's key". For multiple-choice questions the key shows the right letter and, for every wrong letter, what that choice suggests. For true/false rows, check each row. For written answers, give full credit, partial credit where the key allows it, or no credit, and if the child's wrong answer looks like one of the common wrong answers in the key, note its code (RF, PK, CF or INT).

**5. Enter the answers and read the class report.** Open "Enter answers". One row per child. For multiple choice pick the letter the child chose. For true/false rows type one letter per row, for example TFT. For written answers choose full, partial, none, or the code you noted. Leave a cell empty if the child did not answer. Then press "Make the class report". The top of the report lists the wrong ideas that came up most, with what usually helps for each kind.

The answers stay in your browser on that device. To keep them safely, or to move them to another device, press "Download answers (CSV)". You can load the file again later with "Load answers (CSV)".

**6. Reteach, then check.** At the bottom of the class report, press "Make a follow-up set on these mistakes". The page makes a short set with the same kinds of question that caught your class out, but with new numbers, so nobody can just remember last time's answers. Reteach the ideas first, give the follow-up set, and enter the answers the same way. The report then shows, for each mistake, how many children made it the first time and how many made it now. Use the same device for both rounds, or keep the first round's CSV, because the page needs the first round's answers to compare. A drop is encouraging, though not proof on its own: the questions are new, and small classes vary a lot by chance.

## The four kinds of mistake

Every wrong answer in the key is one of four kinds. They come from the Confusion Fingerprint Index, a way of sorting mistakes by the thinking behind them.

| Code | Name | What it means | What usually helps |
|---|---|---|---|
| RF | Recall Failure | The child has little or nothing to build on yet. | Reteach the idea from the start, with a concrete example, before more practice. |
| PK | Partial Knowledge | The direction is right, but steps are missing. | A short worked example, or a checklist of the steps. |
| CF | Confabulation | A confident wrong belief. | Practice alone will not shift it. Show a case where the belief gives an obviously wrong answer and talk it through. |
| INT | Interference | An idea from a nearby topic got used in the wrong place. | Put the two ideas side by side and talk about when each one applies. |

These are suggestions. You know your children better than any table does.

## Honest limits

These are practice items written from original templates that follow the published PISA 2022 maths framework. They are not official PISA questions, and they have not yet been tried with large groups of children, so nobody knows exactly how hard each one is. PISA is for 15-year-olds. These use Class 7 to 9 maths and suit children around Class 8 to 10. The numbers in the tables are made up for practice. The questions are in English and Hindi, and the Hindi is a first draft that a Hindi-medium maths teacher has not yet checked.

## If you coordinate several classes

When several teachers use the same set number, their answer files can be pooled to see how good the questions themselves are. `confusion-mapper pisa-items units.json class1.csv class2.csv ...` reports, for every question, how hard it was, whether stronger students did better on it than weaker ones, which wrong options nobody chooses, and any question where the strongest students picked a wrong option, which usually means a confusing question or a wrong key. Please send these reports back through the issues page. They are how these questions get better.

## If you are a researcher

Every wrong answer's code was fixed in the question template before any child answered, so the class report doubles as data. Download the answers as CSV, keep the set's units (from the command-line version, `confusion-mapper pisa ... --out units.json`), and run `confusion-mapper pisa-score units.json answers.csv` to get each child's Confusion Fingerprint Index: CFI-CF (CF errors over all diagnosed errors), CFI-INT (INT over INT plus RF) and CFI-RF (RF over all diagnosed errors). The web page and the Python package score answers the same way, and a test checks that on random classes.

## Questions or problems

Open an issue at https://github.com/Manik-Maurya/Confusion-Mapper/issues, or write to manikmaurya.in@gmail.com. Reports of a confusing question, a wrong key, or a situation that does not feel familiar to your children are especially welcome.
