---

# UNIT - I: Complete 10-Mark University Exam Breakdown

---

## TOPIC 1: History of Quantum Computing — Importance of Mathematics, Physics, and Biology [10 Marks]

### 1. Historical Evolution and Physical Origins (2.5 Marks)
* **Crises in Classical Physics**: At the turn of the 20th century, classical physical theories (Newtonian mechanics, Maxwellian electrodynamics) failed when applied to atomic and subatomic phenomena. Classical electrodynamics predicted that orbiting electrons would constantly radiate energy and spiral into the nucleus within \\(10^{-11}\\) seconds, while classical thermodynamics produced the **ultraviolet catastrophe** (predicting infinite thermal radiation energy at short wavelengths).
* **Emergence of Quantum Mechanics**: These crises were resolved in the 1920s through modern quantum mechanics developed by Planck, Einstein, Bohr, Heisenberg, Schrödinger, and Dirac. Quantum mechanics successfully explained atomic spectra, chemical bonding, nuclear fusion, semiconductors, and superconductors.
* **Simulating Nature (Feynman & Benioff)**: In 1981, Richard Feynman pointed out a fundamental computational barrier: simulating a quantum mechanical system of \\(n\\) interacting particles on a classical computer requires storing and updating \\(2^n\\) complex probability amplitudes, demanding exponential time and memory. Feynman famously stated: *"Nature isn't classical, dammit, and if you want to make a simulation of nature, you'd better make it quantum mechanical!"*. Paul Benioff (1980) demonstrated that a quantum mechanical system could perform reversible Turing-complete computation.

---

### 2. Importance of Mathematics in Quantum Computation (2.5 Marks)
Quantum information theory relies on linear algebra, group theory, and complex analysis:

```
  Complex Vector Space (Hilbert Space ℂ²)
  ┌─────────────────────────────────────────────────────────┐
  │  State Vector: |ψ⟩ = α|0⟩ + β|1⟩                        │
  │  Inner Product: ⟨φ|ψ⟩ (Calculates overlap & angles)     │
  │  Outer Product: |0⟩⟨1| (Constructs linear operators)     │
  │  Norm & Normalization: ⟨ψ|ψ⟩ = |α|² + |β|² = 1           │
  └─────────────────────────────────────────────────────────┘
```

* **Vector Spaces & Dirac Bra-Ket Notation**: A state vector \\(|\psi\rangle\\) is represented as a column vector (**ket**) in a complex Hilbert space \\(\mathbb{C}^d\\):
  \\[|0\rangle = \begin{bmatrix} 1 \\ 0 \end{bmatrix}, \quad |1\rangle = \begin{bmatrix} 0 \\ 1 \end{bmatrix}\\]
  Its dual vector (**bra**) \\(\langle\psi| = (|\psi\rangle)^\dagger = (\mathbf{\bar{\psi}})^T\\) is a complex-conjugate row vector:
  \\[\langle 0| = \begin{bmatrix} 1 & 0 \end{bmatrix}, \quad \langle 1| = \begin{bmatrix} 0 & 1 \end{bmatrix}\\]
* **Inner Products & Norms**: The inner product \\(\langle\varphi|\psi\rangle\\) computes vector overlap. Physical states must be unit vectors with unit norm:
  \\[\|\psi\| = \sqrt{\langle\psi|\psi\rangle} = 1 \implies |\alpha|^2 + |\beta|^2 = 1\\]
* **Matrix Operations**:
  * **Hermitian Operators (\\(A^\dagger = A\\))**: Represent physical observables with real eigenvalues.
  * **Unitary Matrices (\\(U^\dagger U = I\\))**: Represent closed time evolutions and quantum logic gates, preserving norm and probability.
  * **Tensor Products (\\(\otimes\\))**: Combine multi-qubit state spaces (\\(\mathbb{C}^2 \otimes \mathbb{C}^2 = \mathbb{C}^4\\)).

---

### 3. Importance of Physics in Quantum Computation (2.5 Marks)
* **Subatomic Spin and Two-Level Systems**: Quantum computation requires physical two-level quantum systems (qubits). Examples include electron spin (\\(\text{spin}-1/2\\) with states \\(|\uparrow\rangle, |\downarrow\rangle\\)), photon polarization (\\(|H\rangle, |V\rangle\\)), and energy levels in trapped ions or superconducting Josephson junctions.
* **Stern-Gerlach Experiment**: Demonstrates spatial quantization of angular momentum. Passing silver atoms through an inhomogeneous magnetic field along the \\(\hat{z}\\)-axis splits the beam into two discrete paths (\\(|+Z\rangle\\) and \\(|-Z\rangle\\)). Cascaded experiments reveal that measuring \\(|+Z\rangle\\) atoms along the \\(\hat{x}\\)-axis yields equal portions of \\(|+X\rangle\\) and \\(|-X\rangle\\), proving that a single quantum state exists in a linear superposition of orthogonal basis states.

```text
  [Atom Source] ───> [ SG-Z Apparatus ] ──┬──> |+Z⟩ Beam ───> [ SG-X Apparatus ] ──┬──> |+X⟩ Beam (50%)
                                          │                                         │
                                          └──> |-Z⟩ Beam (50%)                      └──> |-X⟩ Beam (50%)
```

* **Foundational Postulates**:
  1. **Postulate 1 (State Space)**: Closed physical systems live in a complex Hilbert space.
  2. **Postulate 2 (Unitary Evolution)**: Closed state transitions follow \\(|\psi'\rangle = U|\psi\rangle\\).
  3. **Postulate 3 (Measurement)**: Measurement probabilities follow Born's rule \\(P(m) = \langle\psi|M_m^\dagger M_m|\psi\rangle\\).
  4. **Postulate 4 (Composite Systems)**: Combined systems are constructed via tensor products \\(\mathcal{H}_1 \otimes \mathcal{H}_2\\).

---

### 4. Importance of Biology in Quantum Computation (2.5 Marks)
* **Biological Scale vs. Quantum Decoherence**:
  * In machine learning, a single **neuron** is treated as a primitive processing node. However, in quantum computing, a biological cell or neuron is far too large—it contains billions of interacting molecules operating at warm room temperatures (\\(T \approx 300\text{ K}\\)).
  * Thermal interactions cause near-instantaneous **decoherence** (\\(T_2 \sim 10^{-13}\text{ s}\\)), destroying fragile superpositions. Qubits must be isolated at cryogenic temperatures (\\(T \approx 10\text{ mK}\\)) or isolated in ultra-high vacuum traps.

```text
  Scale Comparison:
  ML Perspective:  [ Single Neuron ] = 1 Logical Node
  QC Perspective:  [ Single Neuron ] = ~10¹⁴ Warm Molecules ──> Instant Decoherence!
  QC Requirement:  [ Isolated Subatomic Qubit ] @ Cryogenic Temperatures (10 mK)
```

* **Simulating Biomolecules (Proteomics & Genomics)**:
  * Biological molecules (DNA, RNA, complex proteins, enzymes) rely on non-covalent quantum interactions, hydrogen bonding, and active-site electron correlation.
  * Classically calculating the ground-state energy or folding configuration of a protein containing \\(n\\) interacting orbitals requires diagonalizing a \\(2^n \times 2^n\\) Hamiltonian matrix, which is intractable for \\(n > 50\\). A quantum computer uses \\(n\\) qubits to simulate molecular electronics natively in polynomial time.
* **DNA Computing vs. Quantum Computing**:
  * Leonard Adleman (1994) demonstrated **DNA computing** using single-stranded DNA strings (\\(A, T, G, C\\)) to solve the Directed Hamiltonian Path Problem via parallel chemical hybridization.
  * **Comparison**: DNA computing provides massive *classical* parallelism (\\(\sim 10^{14}\\) test-tube strands reacting simultaneously). However, the physical mass of DNA required grows **exponentially** with problem size (\\(N\\)). Quantum computing uses \\(n\\) qubits to represent \\(2^n\\) complex amplitudes, achieving **exponential algorithmic speedups** without requiring exponential physical matter.

---

## TOPIC 2: Introduction to Quantum Computing — Bits vs. Qubits [10 Marks]

### 1. Conceptual and Mathematical Definition (2.5 Marks)
* **Classical Bit**: A fundamental unit of classical information taking a single deterministic binary value \\(x \in \{0, 1\\}\\). Physically implemented as high/low voltage levels in a transistor.
* **Quantum Bit (Qubit)**: A two-level quantum mechanical system described by a state vector \\(|\psi\rangle\\) in a 2-dimensional complex Hilbert space \\(\mathbb{C}^2\\):
  \\[|\psi\rangle = \alpha |0\rangle + \beta |1\rangle = \alpha \begin{bmatrix} 1 \\ 0 \end{bmatrix} + \beta \begin{bmatrix} 0 \\ 1 \end{bmatrix} = \begin{bmatrix} \alpha \\ \beta \end{bmatrix}\\]
  where \\(\alpha, \beta \in \mathbb{C}\\) are **probability amplitudes**.

```text
                  Classical Bit                        Quantum Qubit
              ┌──────────────────┐                ┌──────────────────┐
              │      State:      │                │      State:      │
              │     0  OR  1     │                │ |ψ⟩ = α|0⟩ + β|1⟩│
              └────────┬─────────┘                └────────┬─────────┘
                       │                                   │
              ┌────────┴─────────┐                ┌────────┴─────────┐
              │ Deterministic    │                │ Superposition &  │
              │ Voltage Switch   │                │ Hilbert Space C² │
              └──────────────────┘                └──────────────────┘
```

* **Normalization Constraint**: Because measurement outcomes must sum to 1 (\\(100\%\\)), physical state vectors must be normalized unit vectors:
  \\[\langle\psi|\psi\rangle = \begin{bmatrix} \bar{\alpha} & \bar{\beta} \end{bmatrix} \begin{bmatrix} \alpha \\ \beta \end{bmatrix} = |\alpha|^2 + |\beta|^2 = 1\\]
* **Numerical Normalization Example**: Given an unnormalized state \\(|\psi\rangle = -4i|0\rangle + 3|1\rangle\\), its squared norm is \\(|-4i|^2 + |3|^2 = 16 + 9 = 25\\). Normalizing yields:
  \\[|\psi_{\text{norm}}\rangle = -\frac{4i}{5}|0\rangle + \frac{3}{5}|1\rangle\\]
  Measurement yields outcome \\(0\\) with probability \\(P(0) = |-4i/5|^2 = 16/25 = 0.64\\) (\\(64\%\\)), and outcome \\(1\\) with probability \\(P(1) = |3/5|^2 = 9/25 = 0.36\\) (\\(36\\)%).

---

### 2. Geometric Representation: The Bloch Sphere (2.5 Marks)
A normalized single-qubit state \\(|\psi\rangle = \alpha|0\rangle + \beta|1\rangle\\) can be re-parameterized using polar spherical coordinates \\((\theta, \phi)\\) on the unit **Bloch sphere**:

\\[|\psi\rangle = \cos\left(\frac{\theta}{2}\right)|0\rangle + e^{i\phi}\sin\left(\frac{\theta}{2}\right)|1\rangle\\]

where \\(\theta \in [0, \pi]\\) represents the polar angle and \\(\phi \in [0, 2\pi)\\) represents the azimuthal angle (global phase \\(e^{i\gamma}\\) is physically unobservable and omitted).

```text
                                 +z (|0⟩)
                                    │
                                    │   • |ψ⟩ = cos(θ/2)|0⟩ + e^(iφ)sin(θ/2)|1⟩
                                    │  /
                                    │ /  θ (Polar angle)
                                    │/───────> +y
                                   / \
                                  /   \ φ (Azimuthal angle)
                                 /     \
                               +x       -z (|1⟩)
```

* **Key Points on the Bloch Sphere**:
  * **North Pole (\\(\theta = 0\\))**: State \\(|0\rangle\\).
  * **South Pole (\\(\theta = \pi\\))**: State \\(|1\rangle\\).
  * **Equator (\\(\theta = \pi/2\\))**: Equal superposition states:
    * \\(\phi = 0 \implies |+\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}}\\)
    * \\(\phi = \pi \implies |-\rangle = \frac{|0\rangle - |1\rangle}{\sqrt{2}}\\)
    * \\(\phi = \pi/2 \implies |+i\rangle = \frac{|0\rangle + i|1\rangle}{\sqrt{2}}\\)
    * \\(\phi = 3\pi/2 \implies |-i\rangle = \frac{|0\rangle - i|1\rangle}{\sqrt{2}}\\)

---

### 3. Multi-Qubit Systems and Exponential Scaling (2.5 Marks)
* **Tensor Product Space**: A composite system of \\(n\\) qubits lives in a \\(2^n\\)-dimensional Hilbert space \\(\mathbb{C}^{2^n} = \mathbb{C}^2 \otimes \mathbb{C}^2 \otimes \dots \otimes \mathbb{C}^2\\).
* **2-Qubit State Vector**:
  \\[|\psi\rangle = \alpha_{00}|00\rangle + \alpha_{01}|01\rangle + \alpha_{10}|10\rangle + \alpha_{11}|11\rangle = \begin{bmatrix} \alpha_{00} \\ \alpha_{01} \\ \alpha_{10} \\ \alpha_{11} \end{bmatrix}\\]
  satisfying \\(\sum_{x \in \{0,1\\}^2} |\alpha_x|^2 = 1\\).
* **Tensor Product Example**: Combining \\(|\phi_1\rangle = -\frac{4i}{5}|0\rangle + \frac{3}{5}|1\rangle\\) and \\(|\phi_2\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}}\\):
  \\[|\psi_{12}\rangle = |\phi_1\rangle \otimes |\phi_2\rangle = -\frac{4i}{5\sqrt{2}}|00\rangle - \frac{4i}{5\sqrt{2}}|01\rangle + \frac{3}{5\sqrt{2}}|10\rangle + \frac{3}{5\sqrt{2}}|11\rangle\\]
* **Exponential Advantage**: \\(n\\) classical bits can store exactly one \\(n\\)-bit number at a time. In contrast, \\(n\\) qubits can store a simultaneous superposition of all \\(2^n\\) basis states:
  * \\(n = 10 \implies 1,024\\) amplitudes.
  * \\(n = 50 \implies \sim 1.12 \times 10^{15}\\) amplitudes (\\(1.12\\) Petabytes of classical memory).
  * \\(n = 300 \implies 2^{300} \approx 2 \times 10^{90}\\) amplitudes (exceeds total estimated elementary particles in the observable universe).

---

### 4. Comprehensive Comparison Table: Bit vs. Qubit (2.5 Marks)

| Feature | Classical Bit | Quantum Qubit |
| :--- | :--- | :--- |
| **Physical Definition** | Discrete two-state switch (\\(0\\) or \\(1\\)) | Two-level quantum system (\\(|\psi\rangle = \alpha|0\rangle + \beta|1\rangle\\)) |
| **Mathematical Domain** | Binary field \\(\mathbb{Z}_2 = \{0, 1\}\\) | 2D Complex Hilbert Space \\(\mathbb{C}^2\\) |
| **State Capacity** | Holds 1 value (\\(0\\) or \\(1\\)) | Holds infinite continuous superpositions on the Bloch sphere |
| **Measurement Impact** | Non-destructive; reading does not alter the state | **Destructive collapse**: Measurement projects state into basis with probability \\(|\alpha|^2, |\beta|^2\\) |
| **Copying Ability** | Arbitrary cloning is freely allowed | **No-Cloning Theorem**: Unknown quantum states cannot be cloned |
| **Multi-Unit Scaling** | \\(n\\) bits store \\(n\\) total bits | \\(n\\) qubits store \\(2^n\\) simultaneous complex amplitudes |
| **Entanglement** | Independent bit strings (no non-local correlations) | **Entangled states** (e.g., Bell state \\(\frac{|00\rangle+|11\rangle}{\sqrt{2}}\\)) exhibit non-local correlations |

---

## TOPIC 3: Classical vs. Quantum Logical Operations [10 Marks]

### 1. Reversibility, Unitarity, and Landauer's Principle (2.5 Marks)
* **Classical Irreversibility**: Classical logic gates like AND, OR, and NAND are lossy and irreversible—they map 2 input bits to 1 output bit. Information is discarded because the inputs cannot be uniquely recovered from the output.
* **Landauer's Principle (1961)**: Erasing or discarding 1 bit of classical information dissipates a minimum heat energy into the environment:
  \\[\Delta Q = k_B T \ln 2\\]
  where \\(k_B\\) is Boltzmann's constant and \\(T\\) is temperature.

```text
  Irreversible Classical Logic:
  Inputs (A, B) ───> [ NAND Gate ] ───> Output (A  NAND B)  ───> Bit Erased! (Heat Dissipated)

  Reversible Quantum Logic:
  Inputs |ψ_in⟩ ───> [ Unitary Gate U ] ───> Output |ψ_out⟩ ───> No Information Erased! (U†U = I)
```

* **Quantum Unitarity**: Closed quantum state evolution is described by linear **unitary operators** \\(U\\) satisfying \\(U^\dagger U = I\\).
* **Properties of Unitary Gates**:
  1. **Reversibility**: Every unitary gate has a deterministic inverse \\(U^{-1} = U^\dagger\\).
  2. **Norm Conservation**: \\(\|U\psi\| = \|\psi\| = 1\\), preserving probability normalization.
  3. **Inner Product Preservation**: \\(\langle U\varphi|U\psi\rangle = \langle\varphi|U^\dagger U|\psi\rangle = \langle\varphi|\psi\rangle\\), preserving geometric angles in Hilbert space.

---

### 2. Single-Qubit Quantum Gates and Matrix Representations (2.5 Marks)

#### **A. Pauli-X Gate (Quantum NOT)**
Flips computational basis states \\(|\alpha\rangle \to |\beta\rangle\\):
\\[X \equiv \begin{bmatrix} 0 & 1 \\ 1 & 0 \end{bmatrix}, \quad X|0\rangle = |1\rangle, \quad X|1\rangle = |0\rangle\\]

#### **B. Pauli-Y Gate**
Combines bit-flip and phase-flip with a complex phase:
\\[Y \equiv \begin{bmatrix} 0 & -i \\ i & 0 \end{bmatrix}, \quad Y|0\rangle = i|1\rangle, \quad Y|1\rangle = -i|0\rangle\\]

#### **C. Pauli-Z Gate (Phase-Flip)**
Leaves \\(|0\rangle\\) unchanged and flips the relative sign of \\(|1\rangle\\):
\\[Z \equiv \begin{bmatrix} 1 & 0 \\ 0 & -1 \end{bmatrix}, \quad Z|0\rangle = |0\rangle, \quad Z|1\rangle = -|1\rangle\\]

#### **D. Hadamard Gate (\\(H\\))**
Creates an equal superposition state from computational basis states:
\\[H \equiv \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix}, \quad H|0\rangle = \frac{|0\rangle + |1\rangle}{\sqrt{2}} = |+\rangle, \quad H|1\rangle = \frac{|0\rangle - |1\rangle}{\sqrt{2}} = |-\rangle\\]

#### **E. Phase Gate (\\(S\\)) and \\(\pi/8\\) Gate (\\(T\\))**
Injects relative complex phases:
\\[S \equiv \begin{bmatrix} 1 & 0 \\ 0 & i \end{bmatrix} = \begin{bmatrix} 1 & 0 \\ 0 & e^{i\pi/2} \end{bmatrix}, \quad T \equiv \begin{bmatrix} 1 & 0 \\ 0 & e^{i\pi/4} \end{bmatrix} \implies T^2 = S\\]

```text
  Single-Qubit Gate Matrix Summary:
  X =     Y = [0 -i]    Z =     H = 1/√2     S =     T = 
              [i  0]                            [0  i]        [0  e^(iπ/4)]
```

---

### 3. Multi-Qubit Gates: CNOT, Toffoli, and Fredkin Gates (2.5 Marks)

#### **A. Controlled-NOT Gate (CNOT / \\(U_{CN}\\))**
Flips the target qubit (\\(B\\)) if and only if the control qubit (\\(A\\)) is \\(|1\rangle\\). Implements \\(U_{CN}|A, B\rangle = |A, B \oplus A\rangle\\):

\\[U_{CN} = \begin{bmatrix} 1 & 0 & 0 & 0 \\ 0 & 1 & 0 & 0 \\ 0 & 0 & 0 & 1 \\ 0 & 0 & 1 & 0 \end{bmatrix}\\]

```text
  Circuit Diagram:                   Truth Table:
  Control A ─────■───── A            | A  B | A' B' |
                 │                   |──────|───────|
                 │                   | 0  0 | 0  0  |
  Target  B ─────⊕───── B ⊕ A        | 0  1 | 0  1  |
                                     | 1  0 | 1  1  |
                                     | 1  1 | 1  0  |
```

---

#### **B. Toffoli Gate (Controlled-Controlled-NOT / \\(C^2X\\))**
A 3-qubit reversible gate that flips target bit \\(C\\) if and only if both control bits \\(A\\) and \\(B\\) are \\(1\\) (\\(C' = C \oplus (A \cdot B)\\)):

\\[U_{\text{Toffoli}} = \begin{bmatrix} 
1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\ 
0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\ 
0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 \\ 
0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 \\ 
0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 \\ 
0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 \\ 
0 & 0 & 0 & 0 & 0 & 0 & 0 & 1 \\ 
0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 
\end{bmatrix}\\]

```text
  Toffoli Circuit Diagram:           Simulating Classical Gates:
  A ─────■───── A                    1. NAND Gate: Set initial C = 1
         │                      Input A, B, C=1 ──> Output C' = 1 ⊕ (A·B) = A NAND B
  B ─────■───── B
         │                           2. FANOUT (Copy): Set initial B = 1, C = 0
  C ─────⊕───── C ⊕ (A·B)            Input A, B=1, C=0 ──> Output (A, 1, A)
```

---

#### **C. Fredkin Gate (Controlled-SWAP / CSWAP)**
A 3-qubit conservative reversible gate. If control bit \\(C = 1\\), it swaps target bits \\(A\\) and \\(B\\) (\\(A'=B, B'=A\\)); if \\(C = 0\\), \\(A\\) and \\(B\\) remain unchanged.
* **Conservation Law**: Conserves the total number of \\(1\text{s}\\) between input and output.

```text
  Fredkin Circuit Diagram:           Billiard Ball Computer Implementation:
  C ──────■────── C                  Implemented using colliding billiard balls
          │                          where presence/absence of a ball represents
  A ──────╳────── A'                 1 or 0, conserving total momentum & kinetic
          │                          energy.
  B ──────╳────── B'
```

\\[U_{\text{Fredkin}} = \begin{bmatrix}
1 & 0 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 1 & 0 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 1 & 0 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 1 & 0 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 1 & 0 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 1 & 0 \\
0 & 0 & 0 & 0 & 0 & 1 & 0 & 0 \\
0 & 0 & 0 & 0 & 0 & 0 & 0 & 1
\end{bmatrix}\\]

---

### 4. Universal Quantum Gate Sets and Gate Identifications (2.5 Marks)

#### **A. Universal Gate Set**
A discrete set of gates is **universal for quantum computation** if any arbitrary \\(n\\)-qubit unitary operator \\(U \in U(2^n)\\) can be approximated to arbitrary precision \\(\epsilon > 0\\) using a finite sequence of gates from that set.

\\[\text{Universal Set} = \{\text{Hadamard }(H), \text{ Phase }(S), \text{ CNOT}, \pi/8\text{ Gate }(T)\}\\]

* **Gottesman-Knill Theorem**: Quantum circuits constructed using only Clifford group gates (\\(\{H, S, \text{CNOT}\\}\\)). Including the non-Clifford \\(T\\)-gate breaks classical simulation bounds, unlocking full quantum computational advantage.
* **Solovay-Kitaev Theorem**: Any single-qubit gate \\(U\\) can be approximated to precision \\(\epsilon\\) using an \\(O(\log^c(1/\epsilon))\\) chain of gates from \\(\{\text{Hadamard}, S, T\\}\\).

---

#### **B. Algebraic Gate Identifications & Proofs**

1. **Verification of \\(H X H = Z\\)**:
   \\[H X H = \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} \begin{bmatrix} 0 & 1 \\ 1 & 0 \end{bmatrix} \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} = \frac{1}{2}\begin{bmatrix} 1 & 1 \\ -1 & 1 \end{bmatrix} \begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} = \begin{bmatrix} 1 & 0 \\ 0 & -1 \end{bmatrix} = Z\\]

2. **Verification of \\(H Z H = X\\)**:
   \\[H Z H = \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} \begin{bmatrix} 1 & 0 \\ 0 & -1 \end{bmatrix} \frac{1}{\sqrt{2}}\begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} = \frac{1}{2}\begin{bmatrix} 1 & -1 \\ 1 & 1 \end{bmatrix} \begin{bmatrix} 1 & 1 \\ 1 & -1 \end{bmatrix} = \begin{bmatrix} 0 & 1 \\ 1 & 0 \end{bmatrix} = X\\]

3. **Toffoli Construction Decomposition**:
   A 3-qubit Toffoli gate can be constructed using exactly **6 CNOT gates** and **9 single-qubit gates** (\\(\{H, T, T^\dagger, S\\}\\)).

```text
  Toffoli Gate Decomposition Circuit:
  Control 1 ──────■───────────────────■─────────────■─────────T────────■───────
                  │                   │             │                  │
  Control 2 ──────┼─────────■─────────┼─────────■───┼─────────T†───────┼───S───
                  │         │         │         │   │                  │
  Target    ───H──⊕───T†────⊕────T────⊕───T†────⊕───T───H───────────────⊕───────
```
