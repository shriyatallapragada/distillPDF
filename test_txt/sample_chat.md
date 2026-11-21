Here is the complete, highly detailed breakdown of all the topics covered in **`qc-notes(mid-2).pdf`**, expanded with textbook derivations from **Nielsen & Chuang (`qc-textbook.pdf`)**. 

All introductory topics from `notes_qc.pdf` (such as the Standard Model of particle physics, Bloch sphere derivations for single-qubit rotations, Deutsch's algorithm, and Grover's search algorithm) have been removed as requested.

---

### 1. Signal Processing, Fourier Analysis, and Digitization

#### **Physics of Periodic Signals and Channel Attenuation**
A periodic signal is composed of fundamental sinusoids and is characterized by its **frequency** (number of cycles per second) and **amplitude** (peak height). When a periodic signal propagates through a physical communication channel, it undergoes **amplitude attenuation** (loss of energy due to resistance and absorption). However, the **frequency remains invariant** across the transmission channel.

#### **Continuous and Discrete Fourier Analysis**
*   **Fourier Transform**: Converts a signal from the continuous time domain \\(x(t)\\) (amplitude vs. time) to the frequency domain \\(X(f)\\) (magnitude vs. frequency).
*   **Inverse Fourier Transform**: Reconstructs the continuous time-domain signal from its frequency spectrum without any loss of information.
*   **Nyquist-Shannon Sampling Theorem**: To digitize a signal without losing information, continuous amplitudes must be recorded at a sampling rate of at least **\\(2n\\) points per sample**, where \\(n\\) is the highest frequency component present in the signal.
*   **Quantization**: Maps continuous sample amplitudes to the nearest discrete quantization levels. Although quantization is inherently a **lossy operation**, combining sampling and quantization converts an analog signal into a discrete digital signal.

#### **Discrete Fourier Transform (DFT) Mathematical Relations**
The Discrete Fourier Transform acts on digitized signals to convert between time and frequency representations:
1.  **Forward DFT (Time to Frequency Domain)**:
    \\[X(k) = \sum_{n=1}^{N} x(n) e^{-\frac{2\pi i k n}{N}}\\]
2.  **Inverse DFT (Frequency to Time Domain)**:
    \\[x(n) = \frac{1}{N} \sum_{k=1}^{N} X(k) e^{\frac{2\pi i k n}{N}}\\]

---

### 2. Classical Public-Key Cryptography: The RSA Algorithm

#### **Mathematical Architecture & Key Generation**
The RSA cryptosystem relies on modular arithmetic over large semi-prime numbers:
1.  **Prime Selection**: Select two distinct large prime numbers, \\(p\\) and \\(q\\).
2.  **Semi-Prime Modulus (\\(N\\))**: Compute \\(N = p \times q\\). Factoring \\(N\\) back into \\(p\\) and \\(q\\) is classically intractable for large key sizes.
3.  **Euler's Totient Function (\\(T\\) or \\(\phi(N)\\))**: Compute \\(T = \phi(N) = (p - 1)(q - 1)\\).
4.  **Encryption Key (\\(E\\))**: Select a prime integer \\(E < T\\) such that \\(\gcd(E, T) = 1\\) (\\(E\\) is co-prime to \\(T\\)).
5.  **Decryption Key (\\(D\\))**: Calculate \\(D\\) as the multiplicative inverse of \\(E\\) modulo \\(T\\):
    \\[E \times D \equiv 1 \pmod T \implies E \cdot D = 1 + k \cdot T\\]

#### **Encryption and Decryption Operations**
*   **Ciphertext Generation**: \\(C = M^E \bmod N\\) (where \\(M\\) is the numerical plaintext).
*   **Plaintext Recovery**: \\(M = C^D \bmod N\\).

#### **Step-by-Step Worked Example (from `qc-notes(mid-2)`)**
*   **Inputs**: Let \\(p = 7\\) and \\(q = 19\\).
*   **Modulus & Totient**: \\(N = 7 \times 19 = 133\\); \\(T = (7-1)(19-1) = 6 \times 18 = 108\\).
*   **Keys**: Choose \\(E = 29\\) (co-prime to 108). Calculate \\(D = 41\\), since \\(29 \times 41 = 1189 = (11 \times 108) + 1 \equiv 1 \pmod{108}\\).
*   **Encryption**: For plaintext \\(M = 60\\):
    \\[C = 60^{29} \bmod 133 = 86 \quad \text{(Ciphertext)}\\]
*   **Decryption**: 
    \\[M = 86^{41} \bmod 133 = 60 \quad \text{(Recovered Plaintext)}\\]

#### **Evolution of Key Standards**
Key length requirements have expanded to maintain security against advancing classical compute power: 1024-bit keys were standard in 2002 (broken by 2006), leading to the 2048-bit standard established in 2014.

---

### 3. Quantum Fourier Transform (QFT) Matrix Algebra

#### **Primitive Roots of Unity**
The solutions to \\(z^n = 1\\) are primitive \\(n\\)-th roots of unity, given by \\(\omega_n^k = e^{\frac{2\pi i k}{n}}\\).
*   **Property 1 (Unit Magnitude)**: \\(|\omega_n^k| = 1\\) (all roots lie equidistant on the unit circle in the complex plane).
*   **Property 2 (Periodic Modulo)**: \\(\omega_n^k = \omega_n^{k \bmod n}\\).

#### **Root Examples**
*   For \\(z^4 = 1\\): Roots are \\(\{\omega_4^0, \omega_4^1, \omega_4^2, \omega_4^3\} = \{1, i, -1, -i\}\\).
*   For \\(z^8 = 1\\): 8 roots distributed at angles \\(\theta \in \{0, \frac{\pi}{4}, \frac{\pi}{2}, \frac{3\pi}{4}, \pi, \frac{5\pi}{4}, \frac{3\pi}{2}, \frac{7\pi}{4}\}\\), giving values \\(\{1, \frac{1+i}{\sqrt{2}}, i, \frac{-1+i}{\sqrt{2}}, -1, \frac{-1-i}{\sqrt{2}}, -i, \frac{1-i}{\sqrt{2}}\}\\).

#### **Unitary DFT Matrix (\\(F_n\\))**
For an \\(n\\)-dimensional state space (\\(n = 2^k\\) qubits), the unitary DFT matrix \\(F_n\\) is defined as:
\\[F_n = \frac{1}{\sqrt{n}} \begin{bmatrix} 
1 & 1 & 1 & \dots & 1 \\ 
1 & \omega_n^1 & \omega_n^2 & \dots & \omega_n^{n-1} \\ 
1 & \omega_n^2 & \omega_n^4 & \dots & \omega_n^{2(n-1)} \\ 
\vdots & \vdots & \vdots & \ddots & \vdots \\ 
1 & \omega_n^{n-1} & \omega_n^{2(n-1)} & \dots & \omega_n^{(n-1)(n-1)} 
\end{bmatrix}\\]

For \\(n = 4\\) (\\(\omega_4 = i\\)), the explicit \\(F_4\\) transformation matrix is:
\\[F_4 = \frac{1}{2} \begin{bmatrix} 
1 & 1 & 1 & 1 \\ 
1 & i & -1 & -i \\ 
1 & -1 & 1 & -1 \\ 
1 & -i & -1 & i 
\end{bmatrix}\\]

#### **Worked QFT Vector Transformation Example**
Transforming the state \\(|\psi\rangle = \frac{|0\rangle + |3\rangle}{\sqrt{2}} = \frac{1}{\sqrt{2}} \begin{bmatrix} 1 \\ 0 \\ 0 \\ 1 \end{bmatrix}\\) using \\(F_4\\):
\\[F_4 |\psi\rangle = \frac{1}{2\sqrt{2}} \begin{bmatrix} 
1 & 1 & 1 & 1 \\ 
1 & i & -1 & -i \\ 
1 & -1 & 1 & -1 \\ 
1 & -i & -1 & i 
\end{bmatrix} \begin{bmatrix} 1 \\ 0 \\ 0 \\ 1 \end{bmatrix} = \frac{1}{2\sqrt{2}} \begin{bmatrix} 2 \\ 1 - i \\ 0 \\ 1 + i \end{bmatrix}\\]
\\[F_4 |\psi\rangle = \frac{|0\rangle}{\sqrt{2}} + \frac{(1-i)|1\rangle}{2\sqrt{2}} + \frac{(1+i)|3\rangle}{2\sqrt{2}}\\]

#### **Textbook Product Representation & Circuit Architecture**
Nielsen & Chuang shows that the QFT acting on computational basis state \\(|j_1 j_2 \dots j_n\rangle\\) factorizes into single-qubit product states:
\\[|j_1 \dots j_n\rangle \longrightarrow \frac{\left(|0\rangle + e^{2\pi i 0.j_n}|1\rangle\right) \left(|0\rangle + e^{2\pi i 0.j_{n-1}j_n}|1\rangle\right) \dots \left(|0\rangle + e^{2\pi i 0.j_1 j_2 \dots j_n}|1\rangle\right)}{2^{n/2}}\\]
*(where \\(0.j_l \dots j_m = \sum_{f=l}^m j_f / 2^{f-l+1}\\) represents binary fraction notation)*.

The circuit requires Hadamard gates, Controlled-\\(R_k\\) phase-shift gates (\\(R_k = \begin{bmatrix} 1 & 0 \\ 0 & e^{2\pi i / 2^k} \end{bmatrix}\\)), and final Swap gates. The quantum circuit complexity is **\\(\Theta(n^2)\\) gates**, compared to the classical Fast Fourier Transform (FFT) requiring \\(\Theta(n 2^n)\\) operations.

---

### 4. Quantum Period-Finding & Shor's Factorization Algorithm

#### **Problem Formulation**
Modular exponentiation functions \\(f(x) = a^x \bmod N\\) exhibit periodic behavior. The **order \\(r\\)** of \\(x\\) modulo \\(N\\) is defined as the smallest positive integer \\(r\\) such that:
\\[x^r \equiv 1 \pmod N\\]

#### **Classical Reduction of Factoring to Order-Finding**
1. Select a random integer \\(x < N\\). If \\(\gcd(x, N) > 1\\), a non-trivial factor is found directly.
2. If \\(\gcd(x, N) = 1\\), call the **Quantum Order-Finding Subroutine** to compute \\(r\\).
3. If \\(r\\) is **even** and \\(x^{r/2} \not\equiv -1 \pmod N\\), then \\(x^r - 1 = (x^{r/2} - 1)(x^{r/2} + 1) \equiv 0 \pmod N\\).
4. Compute non-trivial factors using Euclid's algorithm: **\\(\gcd(x^{r/2} - 1, N)\\)** and **\\(\gcd(x^{r/2} + 1, N)\\)**.

#### **Quantum Order-Finding Circuit & State Evolution**
*   **Control Register 1**: \\(t = 2L + 1 + \lceil \log(2 + 1/2\epsilon) \rceil\\) qubits initialized to \\(|0\rangle^{\otimes t}\\).
*   **Target Register 2**: \\(L = \lceil \log N \rceil\\) qubits initialized to \\(|1\rangle\\).

\\[\begin{array}{rcccl}
|0\rangle^{\otimes t} & \xrightarrow{H^{\otimes t}} & \frac{1}{\sqrt{2^t}} \sum_{j=0}^{2^t-1} |j\rangle |1\rangle & \xrightarrow{U_{x,N}} & \frac{1}{\sqrt{2^t}} \sum_{j=0}^{2^t-1} |j\rangle |x^j \bmod N\rangle \\
& \xrightarrow{\text{Decompose}} & \frac{1}{\sqrt{r 2^t}} \sum_{s=0}^{r-1} \sum_{j=0}^{2^t-1} e^{\frac{2\pi i s j}{r}} |j\rangle |u_s\rangle & \xrightarrow{\text{QFT}^\dagger} & \frac{1}{\sqrt{r}} \sum_{s=0}^{r-1} |\widetilde{s/r}\rangle |u_s\rangle
\end{array}\\]

Measuring Register 1 yields an integer outcome \\(y \approx \frac{s}{r} \cdot 2^t\\). The classical **Continued Fractions Algorithm** processes \\(y/2^t\\) to extract the exact order \\(r\\) in \\(O(L^3)\\) steps.

#### **Numerical Examples**
*   **Notes Example (\\(N=15, x=13\\))**:
    Sequence \\(13^k \bmod 15 \implies \{1, 13, 4, 7, 1, 13, \dots\}\\) giving period \\(r = 4\\).
    Factors: \\(\gcd(13^{4/2} + 1, 15) = \gcd(170, 15) = \mathbf{5}\\), and \\(15/5 = \mathbf{3}\\).
*   **Textbook Box 5.4 Example (\\(N=15, x=7\\))**:
    Register 1 uses \\(t = 11\\) qubits (\\(2^t = 2048\\)).
    Sequence \\(7^k \bmod 15 \implies \{1, 7, 4, 13\}\\), giving \\(r = 4\\).
    Implicit measurement collapses Register 1; inverse QFT produces sharp peaks at \\(y \in \{0, 512, 1024, 1536\}\\).
    For \\(y = 1536\\): \\(\frac{1536}{2048} = \frac{3}{4} \implies r = 4\\).
    Factors: \\(\gcd(7^2 - 1, 15) = \mathbf{3}\\) and \\(\gcd(7^2 + 1, 15) = \mathbf{5}\\).

---

### 5. Bio-Quantum Connections: Genomics & Proteomics

#### **Cellular Structure & Genomic Organization**
*   **Cell Components**: Nucleus, nucleolus, and organelles. Human cells contain 23 pairs of chromosomes, encoding ~20,000 (males) to ~23,000 (females) genes.
*   **DNA Base Pairs**: Human DNA contains ~3 billion base pairs.
    *   **Purines (Double-Ring)**: Adenine (\\(A\\), \\(\text{C}_5\text{H}_5\text{N}_5\\)), Guanine (\\(G\\), \\(\text{C}_5\text{H}_5\text{N}_5\text{O}\\)).
    *   **Pyrimidines (Single-Ring)**: Cytosine (\\(C\\), \\(\text{C}_4\text{H}_5\text{N}_3\text{O}\\)), Thymine (\\(T\\), \\(\text{C}_5\text{H}_6\text{N}_2\text{O}_2\\)).
    *   **Complementary Pairing**: \\(A-T\\) and \\(G-C\\).
*   **Nucleosides vs. Nucleotides**:
    *   Nucleoside = Base + Sugar.
    *   Nucleotide = Base + Sugar + Phosphate.

#### **RNA Translation & Proteomics**
*   **RNA Base Replacement**: In RNA, Thymine (\\(T\\)) is replaced by Uracil (\\(U\\), \\(\text{C}_4\text{H}_4\text{N}_2\text{O}_2\\)).
*   **RNA Types**: mRNA (messenger RNA), rRNA (ribosomal RNA), tRNA (transfer RNA).
*   **Protein Synthesis**: 1 Codon (3 mRNA bases) + 1 Anti-codon (tRNA) = 1 Amino Acid. Amino acids link via **peptide bonds**.
*   **Functional Classes**:
    *   **Enzymes**: Manufactured and consumed at the same biological location.
    *   **Hormones**: Manufactured at one site and transported to be utilized at another.

---

### 6. Quantum Key Distribution (QKD) & The BB84 Protocol

#### **Photonic Encoding & Measurement Bases**
QKD encodes key bits into single-photon polarization states:
*   **Rectilinear Basis (\\(+\\))**: \\(|0\rangle \to \uparrow\\) (vertical \\(90^\circ\\)), \\(|1\rangle \to \rightarrow\\) (horizontal \\(0^\circ\\)).
*   **Diagonal Basis (\\(\times\\))**: \\(|+\rangle \to \nearrow\\) (\\(45^\circ\\)), \\(|-\rangle \to \nwarrow\\) (\\(135^\circ\\)).

#### **BB84 Protocol Workflow (Bennett & Brassard, 1984)**
1.  Alice generates a random bit string \\(a\\) and a random basis string \\(b\\).
2.  Alice transmits photons over the quantum channel encoded in basis \\(b\\).
3.  Bob measures incoming photons choosing random bases \\(b'\\).
4.  **Public Sifting**: Over a classical channel, Alice and Bob compare \\(b\\) and \\(b'\\). They keep bits where \\(b = b'\\) and discard mismatched bases.
5.  **Eavesdropping Detection**: By the No-Cloning Theorem and Proposition 12.18 (Information Gain Implies Disturbance), any interception by Eve alters non-orthogonal states, introducing a detectable Bit Error Rate (BER) on check bits.
6.  **Classical Post-Processing**: Information Reconciliation (error correction) and Privacy Amplification (hash compression) eliminate Eve's mutual information.

---

### 7. Quantum Error Correction, Graph States, & Fault-Tolerance

#### **Decoherence and Error Discretization**
Environmental coupling destroys fragile superpositions (**decoherence**). While classical error correction works on discrete bits, quantum error correction handles continuous errors by projecting arbitrary rotations onto discrete Pauli errors \\(\{I, X, Y, Z\}\\) during syndrome measurement.

#### **3-Qubit Bit-Flip Code**
*   **Encoder**: Concatenates \\(|\psi\rangle = \alpha|0\rangle + \beta|1\rangle\\) with two \\(|0\rangle\\) ancilla qubits via CNOT gates to form \\(\alpha|000\rangle + \beta|111\rangle\\).
*   **Syndrome Measurement**: Measures commuting parity observables \\(Z_1 Z_2\\) and \\(Z_2 Z_3\\) using ancilla qubits:

| Observable \\(Z_1 Z_2\\) | Observable \\(Z_2 Z_3\\) | Error Syndrome | Error Location & Recovery |
| :---: | :---: | :---: | :--- |
| \\(+1\\) | \\(+1\\) | \\(00\\) | No Error (\\(I \otimes I \otimes I\\)) |
| \\(-1\\) | \\(+1\\) | \\(10\\) | Bit-flip on Qubit 1 (\\(X_1\\)) |
| \\(-1\\) | \\(-1\\) | \\(11\\) | Bit-flip on Qubit 2 (\\(X_2\\)) |
| \\(+1\\) | \\(-1\\) | \\(01\\) | Bit-flip on Qubit 3 (\\(X_3\\)) |

#### **3-Qubit Phase-Flip & 9-Qubit Shor Code**
*   **3-Qubit Phase-Flip Code**: Encodes \\(|0\rangle \to |+++\rangle, |1\rangle \to |---\rangle\\). Hadamard transforms convert phase flips (\\(Z\\)) into bit flips (\\(X\\)) for detection via \\(X_1 X_2\\) and \\(X_2 X_3\\).
*   **9-Qubit Shor Code**: Concatenates phase-flip and bit-flip codes:
    \\[|0_L\rangle = \frac{(|000\rangle+|111\rangle)(|000\rangle+|111\rangle)(|000\rangle+|111\rangle)}{2\sqrt{2}}\\]
    \\[|1_L\rangle = \frac{(|000\rangle-|111\rangle)(|000\rangle-|111\rangle)(|000\rangle-|111\rangle)}{2\sqrt{2}}\\]
    It is the smallest code that protects against arbitrary single-qubit errors (\\(X, Y,\\) or \\(Z\\)).

#### **Graph States and Graph Codes**
*   **Graph State (\\(|G\rangle\\))**: Defined on graph \\(G = (V, E)\\) with vertices initialized in \\(|+\rangle^{\otimes |V|}\\) and connected by Controlled-\\(Z\\) (\\(CZ\\)) edges:
    \\[|G\rangle = \prod_{(u,v) \in E} CZ_{uv} |+\rangle^{\otimes |V|}\\]
*   **Stabilizer Generators**: Unique \\(+1\\) eigenstate of commuting operators \\(K_v = X_v \prod_{u \in N(v)} Z_u\\).

#### **Fault-Tolerant Quantum Computation**
*   **Transversal Gates**: Operations applied bitwise between corresponding qubits in encoded blocks (e.g., \\(H^{\otimes 7}, \text{CNOT}^{\otimes 7}\\) on Steane code). Transversal gates prevent single errors from propagating to multiple qubits within the same code block.
*   **Non-Transversal Gates**: Gates like \\(T\\) (\\(\pi/8\\)) cannot be transversal on stabilizer codes (Eastin-Knill theorem) and are realized via fault-tolerant magic state distillation.
*   **Threshold Theorem**: If physical gate error rates fall below a critical threshold \\(p_{\text{th}} \sim 10^{-5}\\), recursive code concatenation allows arbitrarily long quantum computations with arbitrary accuracy.

#### **Classical vs. Quantum Information Theory**
*   **Entropy**: Shannon Entropy \\(H(X) = -\sum p_x \log p_x\\) vs. von Neumann Entropy \\(S(\rho) = -\text{Tr}(\rho \log \rho)\\).
*   **Cloning & Capacity**: Classical bits can be cloned freely, whereas quantum states are restricted by the **No-Cloning Theorem**. Classical noiseless compression is governed by Shannon's theorem, while quantum state compression follows **Schumacher's Quantum Noiseless Coding Theorem**.

### 1. Overview and Core Significance of Shor's Algorithm
Shor's algorithm (developed by Peter Shor in 1994) is a quantum algorithm that solves integer factorization in **polynomial time** \\(O(L^3)\\), where \\(L = \lceil \log N \rceil\\) is the bit length of the composite number \\(N\\). 

Classically, the best-known factoring algorithm—the General Number Field Sieve—requires sub-exponential time \\(O(\exp(c L^{1/3} (\log L)^{2/3}))\\), making the factorization of large numbers computationally intractable on classical computers. Shor's algorithm provides an **exponential speedup** over classical methods, directly threatening public-key cryptosystems like RSA.

The key breakthrough of Shor's algorithm is reducing the hard classical problem of **integer factorization** into the quantum problem of **period-finding (or order-finding)**.

---

### 2. The Classical Reduction: Factoring to Period-Finding

To factor a composite semi-prime integer \\(N = p \times q\\), Shor's algorithm combines classical number theory with a quantum subroutine:

1. **Pick a Random Integer**: Choose a random integer \\(x\\) such that \\(1 < x < N\\).
2. **Euclid's GCD Check**: Compute \\(\gcd(x, N)\\) classically using Euclid's algorithm. If \\(\gcd(x, N) > 1\\), a non-trivial factor has been found directly without quantum processing.
3. **Define the Periodic Function**: If \\(\gcd(x, N) = 1\\), consider the modular exponentiation function \\(f(k) = x^k \bmod N\\). This function is periodic with an unknown **order or period \\(r\\)**, which is the smallest positive integer such that:
   \\[ x^r \equiv 1 \pmod N \\]
4. **Quantum Period-Finding**: The quantum computer is invoked as a subroutine to calculate the period \\(r\\).
5. **Factor Extraction**: If \\(r\\) is **even** and \\(x^{r/2} \not\equiv -1 \pmod N\\), we rewrite the modular congruence as:
   \\[ x^r - 1 \equiv 0 \pmod N \implies \left(x^{r/2} - 1\right)\left(x^{r/2} + 1\right) \equiv 0 \pmod N \\]
   Computing \\(\gcd\left(x^{r/2} - 1, N\right)\\) and \\(\gcd\left(x^{r/2} + 1, N\right)\\) classically yields the non-trivial prime factors \\(p\\) and \\(q\\) of \\(N\\) with probability \\(P \ge 1/2\\).

---

### 3. How QFT and Period-Finding Work Quantum-Mechanically

Finding the period \\(r\\) classically requires evaluating \\(x^k \bmod N\\) sequentially for many values of \\(k\\), taking exponential time. The quantum computer finds \\(r\\) in a single unified execution using **Quantum Parallelism** and the **Quantum Fourier Transform (QFT)**.

#### **System Setup & State Evolution**
The quantum circuit utilizes two registers:
* **Control Register 1**: \\(t = 2L + 1 + \lceil \log(2 + 1/2\epsilon) \rceil\\) qubits initialized to \\(|0\rangle^{\otimes t}\\).
* **Target Register 2**: \\(L = \lceil \log N \rceil\\) qubits initialized to \\(|1\rangle\\).

```text
Register 1 (t qubits): |0⟩^{\otimes t} ───[ H^{\otimes t} ]───■───[ QFT† ]─── [ Measure ] ──> y ──> Continued Fractions ──> r
                                                       │
Register 2 (L qubits): |1⟩ ─────────────────────────[U_{x,N}]──────────────────────────────────────────────────
```

1. **Superposition Generation**: Hadamard gates \\(H^{\otimes t}\\) are applied to Register 1 to create an equal superposition of all possible exponent values \\(j \in \{0, 1, \dots, 2^t - 1\}\\):
   \\[ |\psi_1\rangle = \frac{1}{\sqrt{2^t}} \sum_{j=0}^{2^t-1} |j\rangle |1\rangle \\]
2. **Modular Exponentiation Oracle (\\(U_{x,N}\\))**: The controlled unitary transformation \\(U_{x,N}\\) maps \\(|j\rangle|1\rangle \to |j\rangle|x^j \bmod N\rangle\\), computing \\(f(j)\\) across all superposition states simultaneously:
   \\[ |\psi_2\rangle = \frac{1}{\sqrt{2^t}} \sum_{j=0}^{2^t-1} |j\rangle |x^j \bmod N\rangle \\]
3. **Application of Inverse QFT (\\(\text{QFT}^\dagger\\))**:
   * The values in Register 2 repeat with period \\(r\\).
   * Applying the **Inverse Quantum Fourier Transform** to Register 1 converts phase information into constructive interference peaks centered at integer multiples of \\(\frac{2^t}{r}\\).
   * The QFT maps the periodic structure of amplitudes into readable basis states:
     \\[ |\psi_3\rangle = \text{QFT}^\dagger |\psi_2\rangle \approx \frac{1}{\sqrt{r}} \sum_{s=0}^{r-1} \left| \widetilde{\frac{s}{r}} \right\rangle |u_s\rangle \\]
4. **Measurement & Continued Fractions**:
   * Measuring Register 1 produces an integer result \\(y\\), where \\(\frac{y}{2^t}\\) closely approximates the fraction \\(\frac{s}{r}\\) for a random integer \\(s \in \{0, \dots, r-1\}\\).
   * Since \\(\left|\frac{s}{r} - \frac{y}{2^t}\right| \le \frac{1}{2r^2}\\), applying the classical **Continued Fractions Algorithm** to \\(\frac{y}{2^t}\\) efficiently extracts the exact order \\(r\\) in \\(O(L^3)\\) steps.

---

### 4. How Shor's Algorithm Breaks RSA Cryptography

#### **RSA Architecture**
The RSA public-key cryptosystem works as follows:
1. Alice selects two large prime numbers \\(p\\) and \\(q\\), computing semi-prime modulus \\(N = p \times q\\) and Euler's totient \\(T = \phi(N) = (p-1)(q-1)\\).
2. She selects a public encryption key \\(E\\) co-prime to \\(T\\) (\\(\gcd(E, T) = 1\\)).
3. She calculates the private decryption key \\(D\\) such that \\(E \times D \equiv 1 \pmod T\\).
4. Messages are encrypted via ciphertext \\(C = M^E \bmod N\\) and decrypted via \\(M = C^D \bmod N\\).

Classical security rests entirely on the assumption that factoring \\(N\\) into \\(p\\) and \\(q\\) is hard, preventing an attacker from finding \\(T\\) or calculating \\(D\\).

#### **Two Ways Shor's Algorithm Breaks RSA**

* **Method 1: Direct Prime Factorization**:
  An attacker (Eve) uses Shor's period-finding subroutine to factor \\(N = p \times q\\) in polynomial time \\(O(L^3)\\). Once \\(p\\) and \\(q\\) are known, Eve calculates \\(T = (p-1)(q-1)\\) and computes the exact private decryption key \\(D = E^{-1} \pmod T\\) using Euclid's algorithm, breaking the cryptosystem completely.

* **Method 2: Order-Finding on Ciphertext (Without Factoring \\(N\\))**:
  Eve can bypass prime factorization altogether by measuring the period \\(r\\) of the received ciphertext \\(C = M^E \bmod N\\) such that \\(C^r \equiv 1 \pmod N\\). Since \\(r\\) divides \\(T = \phi(N)\\), \\(E\\) is guaranteed to have a multiplicative inverse \\(d' \equiv E^{-1} \pmod r\\). Eve then decrypts the ciphertext directly by computing:
  \\[ C^{d'} \bmod N = \left(M^E\right)^{d'} \bmod N = M^{1 + kr} \bmod N = M \pmod N \\]
  This allows Eve to recover the original message \\(M\\) without ever needing to determine the private key \\(D\\) or the individual primes \\(p\\) and \\(q\\).

---

💡 **Next Step:** Would you like to work through a step-by-step numerical calculation of Shor's algorithm for factoring \\(N = 21\\) or examine how Quantum Key Distribution (QKD) provides post-quantum security against Shor's algorithm?