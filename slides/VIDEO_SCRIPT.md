# Video script (read aloud, about 4.5 minutes)

Read each block while that slide is on screen, then move to the next slide.
Total: 638 words. At about 150 words a minute that is 4.3 minutes, plus the 20-second demo clip on slide 7.


## 1. cover  (36 words)

Hi, I’m Neel Gurram. During brain surgery the brain moves, and the surgeon’s map goes wrong. My project, Anchor, uses a quantum computer to help fix that map, and I tested it on 22 real patients.

## 2. problem  (66 words)

Before surgery, the patient gets an MRI, and a navigation system uses it like a GPS for the surgeon’s tools. But once the skull is opened, the brain shifts, by up to 2 centimetres. Now the map is wrong, so the surgeon can leave tumour behind or cut healthy brain. The only full fix today is an MRI machine in the operating room, which costs millions.

## 3. hard  (48 words)

A cheaper fix is ultrasound. We find the same spots on the MRI and on a live ultrasound, and each arrow shows how far that spot moved. But ultrasound is blurry, so some matches are wrong, like this red one. And one wrong match bends the whole map.

## 4. solution  (63 words)

That’s where Anchor comes in. Right matches all move together, so they agree with each other. Anchor keeps the biggest group that agrees and drops the rest. Then it bends the map onto the good matches, and checks its own work: it hides one match at a time and sees if the others still predict it. If they don’t, it warns the surgeon.

## 5. shape  (67 words)

Choosing which matches to keep is a known hard puzzle called maximum clique, and we write it as a QUBO so a quantum computer can work on it. Each match is a qubit: keep or drop. In superposition the qubits hold every possible group at once. We measure thousands of times and keep the best group. To be honest, today a normal computer is just as good.

## 6. result  (57 words)

Here’s what that looks like on a real patient. Solid is the real brain, dashed is the surgeon’s map. With no fix, the map is 19.6 millimetres off. Trusting every match only gets it to 16.5, and Anchor’s alarm says don’t trust it. With Anchor, it’s 1.6 millimetres off, and Anchor says the map can be trusted.

## 7. demo  (51 words)

Here’s the app on that same patient. Watch: the skull opens, the map goes wrong, trusting every match fails and the alarm fires, then the quantum circuit picks the matches that agree and the map comes back to 1.6 millimetres. The real IBM chip gives the same answer.

## 8. benchmark  (56 words)

We tested it on all 22 patients in a public dataset, RESECT: 264 tests, graded on landmarks Anchor never saw. Trusting every match left the map 5.6 millimetres off, worse than no fix. Anchor got it to about 2.2, on quantum and normal computers alike. A standard method, RANSAC, did slightly better, and we report that.

## 9. hardware  (85 words)

I built it in Qiskit: a parameterized QAOA circuit, tuned in a hybrid loop with a normal computer, and run with the Sampler. Then we ran 48 puzzles on IBM’s real ibm_fez chip. In 42 of them the chip’s best answer was perfect, and the map was as good as a normal computer’s. It got 83 percent of the valid answers our noise model predicted, six times better than random guessing. So we compared it with a simulator, analysed the noise, and used error suppression.

## 10. revisit  (71 words)

So, honestly, quantum ties a normal computer today. For quantum to win, chips need about eight times fewer errors, 80 to 200 qubits, and answers in under a second; our cloud run took hours. What’s missing: Anchor doesn’t read real ultrasound images yet, and a hospital would need FDA approval. With another month, I’d read real ultrasound images, make the puzzle smart enough to beat RANSAC, and try a quantum annealer.

## 11. close  (38 words)

In one sentence: when the brain moves during surgery, Anchor finds the matches that agree, fixes the surgeon’s map, and warns when the fix can’t be trusted. I built this solo. Thank you, I’m happy to take questions.
