
# Superconductivity in Electron Liquids: Precision Many-Body Treatment of Coulomb Interaction  

Xiansheng Cai, \(^{1,2}\) Tao Wang, \(^{2,3}\) Shuai Zhang, \(^{1}\) Tiantian Zhang, \(^{1,*}\) Andrew Millis, \(^{4,5}\) Boris V. Svistunov, \(^{2}\) Nikolay V. Prokof'ev, \(^{2}\) and Kun Chen \(^{1,4,\dagger}\) \(^{1}\) Institute of Theoretical Physics, Chinese Academy of Sciences, Beijing 100190, China \(^{2}\) Department of Physics, University of Massachusetts, Amherst, MA 01003, USA \(^{3}\) Institute of Physics, Chinese Academy of Sciences, Beijing 100190, China \(^{4}\) Center for Computational Quantum Physics, Flatiron Institute \(^{5}\) Department of Physics, Columbia University, New York (Dated: January 8, 2026)  

More than a century after its discovery, the theory of superconductivity in conventional metals has remained incomplete. While the crucial importance of the electron- phonon coupling is understood, a theoretically controlled first- principles treatment of the Coulomb interaction has yet to be formulated. The downfolding approximation widely employed in existing ab initio calculations of conventional superconductors is based on a phenomenological replacement of the Coulomb interaction by a repulsive pseudopotential, \(\mu^{*}\) , while ambiguities in approximating the electron- phonon coupling in the presence of dynamical Coulomb interactions have remained unresolved. We address these limitations through an effective field theory approach based on integrating out high- energy electronic degrees of freedom using variational Diagrammatic Monte Carlo. Applying the theory to the uniform electron gas establishes a quantitative microscopic procedure to implement the downfolding approximation, define the pseudopotential, and express the effect of the dynamical Coulomb interaction on the electron- phonon coupling through the electron vertex function. We find that the bare pseudopotential is significantly larger than the conventional, phenomenologically defined values. These results provide improved estimates of the Coulomb pseudopotential in simple metals and enable tests of the accuracy of the density functional perturbation theory in describing the effective electron- phonon coupling. We present an ab initio workflow for computing the superconducting \(T_{c}\) from the precursory Cooper flow of the anomalous vertex, that allows us to infer the superconducting transition temperature from normal state calculations, enabling reliable estimates even of very low \(T_{c}\) values (including superconductivity in the proximity of quantum phase transition points) beyond the reach of conventional methods. We validate our approach by computing \(T_{c}\) for simple metals without empirical tuning of parameters, resolve long- standing discrepancies between the theory and experiment, and predict a pressure- induced quantum phase transition from a superconducting to a non- superconducting state in Al as the pressure is increased above a critical value \(\sim 60\) GPa. We propose that ambient- pressure Mg and Na are proximal to a similar critical point. Our work establishes a controlled ab initio framework for electron- phonon superconductivity beyond the weak electron correlation limit, paving the way for reliable \(T_{c}\) calculations and design of novel superconducting materials.  

## I. INTRODUCTION  

Superconductivity (SC), a macroscopic quantum phenomenon with far- reaching fundamental physics and technological implications, is a focal point of condensed matter research. For the first half century after its discovery, lack of a theoretical basis for understanding the physics of interacting electrons inhibited the development of a theory of superconductivity. Following the work of Fröhlich [1] and the experimental confirmation by the Rutgers and NBS groups [2, 3], the importance of the electron phonon interaction was recognized, but how it competed with Coulomb repulsion was not clear. Bardeen, Cooper and Schrieffer (BCS) then provided our basic understanding of superconductivity in terms of a phonon- mediated attraction leading to a pairing instability [4- 6]. The original BCS paper took the radical step of ignoring Coulomb effects altogether but among many other important concepts introduced the idea that if a weak pairing interaction existed at some energy scale, its importance increased as the scale was lowered. This meant that superconductivity should be understood as a low energy instability of the electron gas and that the competition was between a phonon- mediated interaction and an effective electron- electron repulsion defined at the scale of the phonon frequency. This insight motivated studies of the effective Coulomb interaction in the pairing (Cooper) channel at low energy, obtained by "downfolding" the fundamental Coulomb interaction. The first downfolding argument was provided by Bogoliubov, Tolmachev, and Shirkov [7, 8] who showed that the same Cooper logarithm that leads to SC for attractive interactions will renormalize a frequency independent local Coulomb repulsion to the weak coupling limit at low energies. The resulting dimensionless parameter, \(\mu^{*} > 0\)



describing the effect of Coulomb interactions in the pairing channel at the scale of the phonon frequency, was later named the "pseudopotential" by Morel and Anderson [9]).  

The microscopic description of phonon- mediated attraction is encoded in the Migdal- Eliashberg theory, which goes beyond the original BCS theory by rigorously treating the dynamic electron- phonon (e- ph) interaction and provides the foundational framework for understanding phonon- mediated superconductors [10- 12]. While the original formulation [10, 11] focused on the e- ph interaction, subsequent developments [8, 9] incorporated Coulomb repulsion via the static pseudopotential \(\mu^{*}\) and following modern convention we refer to this combined theory as "Migdal- Eliashberg" or ME theory. ME theory as conventionally implemented relies on a "down- folding" approximation [8, 11- 17] that takes advantage of the large energy scale separation between a typical Fermi energy, \(E_{\mathrm{F}}\) , and a typical phonon frequency \(\omega_{\mathrm{D}}\) to project the equations into the low- energy subspace defined by an effective Fermi- surface theory of quasiparticles, replacing bare e- ph interactions with screened effective e- ph coupling, \(\lambda\) [11, 12]. It is important to note that although the adiabatic limit (when \(\omega_{\mathrm{D}} / E_{\mathrm{F}} \ll 1\) ) justifies the formulation in terms of a downfolded theory, as it is currently implemented many aspects of the ME theory remain semi- phenomenological. Coulomb- induced quasiparticle renormalizations are neglected, as are possible renormalizations of the electron- phonon coupling by Coulomb fluctuations as well as non- local effects coming from a scale dependence of screening, particularly pronounced in two dimensional materials [18]. The Coulomb pseudopotential \(\mu^{*}\) is chosen in an ad- hoc or phenomenological manner [19]. This creates critical challenges both for first- principles predictions of transition temperatures and for quantifying unconventional, i.e. not involving e- ph coupling, pairing mechanisms.  

Perhaps the most controversial issue is the magnitude and sign of \(\mu^{*}\) . The first theoretical estimates were based on the unphysical approximation that Coulomb interactions are screened at all frequencies. When this approximation was subsequently removed by employing the "random phase" approximation (RPA) to compute the more physical dynamically screened interaction, Takada [20, 21] and Rietschel and Sham [22] found that the dynamical effects of the Coulomb potential may lead to attractive \(\mu^{*} < 0\) and s- wave superconductivity even in the absence of phonons, if the electron- electron interaction is strong enough. Recent studies again within the RPA, now extended to all paring channels [23- 25] confirm the validity of this theoretical conclusion.  

The RPA- based finding of purely electronically mediated superconductivity is inconsistent with a large body of empirical evidence, and is also internally inconsistent. For a recent discussion see Ref. [26]. In the electron gas, the strength of the Coulomb interaction is parametrized by the dimensionless Wigner- Seitz radius \(r_{\mathrm{s}} = \left(\frac{9\pi}{4}\right)^{1 / 3}\frac{me^{2}}{\hbar^{2}k_{\mathrm{F}}}\) , in effect the ratio of interaction to  

kinetic energies at the scale of the interelectron spacing. The RPA is a good approximation for \(r_{\mathrm{s}} \lesssim 1\) while the Coulombic pairing was found at \(r_{\mathrm{s}} \gtrsim 2\) where beyond- RPA effects, including vertex corrections and renormalization of the single- particle propagators [23, 27], may be important.  

Due to these theoretical uncertainties, \(\mu^{*}\) is often treated as an adjustable parameter, with values empirically chosen between 0.1 and 0.2 to reconcile theory with experiments. This range leads to large (sometime orders of magnitude) uncertainty when predicting \(T_{c}\) in materials where SC depends on a delicate balance between phonon- mediated attraction and \(\mu^{*}\) . For instance, ME theory predictions for \(T_{c}\) in aluminum, a workhorse of superconducting electronics for transition- edge sensors [28] and qubits [29], deviate from experiments by a factor of two [30], while for elemental lithium the theory overestimates \(T_{c}\) by three orders of magnitude [31- 33]. These discrepancies severely limit the possibility of reliable predictive design for quantum devices requiring precise control of energy gaps and thermal noise. Even more strikingly, some transition- metal based compounds (e.g., V, \(\mathrm{Nb}_{3} \mathrm{Sn}\) [34]), alkali- doped picene [35], and high- pressure hydrides [36] are best described by \(\mu^{*}\) values from 0.2 to 0.5, well outside of the limits following from the static [9] and dynamic RPA [27, 37, 38]. While more advanced theories such as the T- matrix approximation [39, 40] have been proposed to address the discrepancy, their development rather underscores the need for a systematic precise microscopic theory of \(\mu^{*}\) as opposed to the case- selective use of uncontrolled approximations.  

Equally important is accurate treatment of the effective coupling, \(\lambda\) , which quantifies the phonon- mediated attraction between quasiparticles at the Fermi surface within the downfolding procedure. State- of- the- art ab initio methods, such as the density functional perturbation theory (DFPT) [15- 17, 30, 41], calculate \(\lambda\) from the ground- state energy response to lattice distortions, an approximation validated for weakly correlated superconductors [19]. However, it remains unknown how accurate this proxy is for correlated systems, where strong renormalization effects are expected to alter effective e- ph interactions and thus SC [23, 27, 38, 42]. Removing this uncertainty is crucial for extending the predictive power of such a method as density functional theory plus dynamical mean- field theory (DFT+DMFT) [43- 50] to strongly correlated superconductors.  

The downfolded ME framework also faces conceptual challenges on top of practical difficulties with precise evaluation of \(\mu^{*}\) and \(\lambda\) . The conventional approach becomes inadequate in the strong e- ph coupling regime, e.g. in high- pressure hydrides with large quantum nuclear effects [36], near structural transitions, or due to the formation of bipolarons [51- 53].  

These limitations have motivated efforts to transcend the downfolding procedure altogether. Richardson and Ashcroft suggested solving the system of ME equations "as is" with full momentum- frequency dependence of both



the e- ph and screened (at the RPA level) e- e interactions [31, 54]. Their approach successfully predicted \(T_{c}\) for lithium [33], but its reliance on the RPA casts doubt on its applicability for electron densities relevant to most metals. This and the large computational cost have prevented this method from becoming widely adopted (but see [55] for recent applications in two dimensions). Superconducting DFT [56- 58] offers an alternative by generalizing DFT to include the superconducting order parameter, with screening effects approximated by the RPA- based ansatz. Recently, it was adapted within the ME framework [59], offering a potentially fruitful avenue for future research. However, such issues as contributions coming from spin fluctuations [60] and vertex corrections to the effective coupling remain unresolved, and the method as implemented to date relies on the RPA. To our knowledge, a consistent and quantitatively accurate microscopic treatment of Coulomb effects in the theory of SC has not yet been achieved.  

In this paper we present a theory of the Cooper (pairing) instability in an interacting electron gas coupled to phonons. The theory is founded on the separation of scales ideas that justify the Migdal- Eliashberg and Fermi Liquid theories but takes advantages of modern developments in the effective field theory of interacting fermion systems and of recent progress in diagrammatic Monte Carlo that enables calculations of relevant quantities, so that we are able to obtain a downfolded ME formulation beyond the limit of weak correlations. Our effective low- energy theory involves Fermi- surface quasiparticles coupled to phonons with precise expressions for Coulomb pseudopotential \(\mu^{*}\) and electron- phonon coupling \(\lambda\) in terms of the electron vertex functions computed via modern many- body techniques. Our work reconciles the contradiction between phenomenological and RPA treatments of the problem by validating the use of the local, instantaneous, and universal \(\mu^{*}\) for conventional materials and resolves issues of the renormalization of electron- phonon coupling and the proper placement of the quasiparticle weight factor.  

Importantly, we also provide limits of validity of the theory, which fails at extremely high electron densities when the plasmon frequency, \(\omega_{\mathrm{p}}\) , softens, in 2D when the plasmon mode is no longer gapped, in materials with soft collective excitations emerging from strong correlations, and systems with low conduction electron density, revealing regimes where the dynamic nature of screening is most relevant. While 3D electron densities corresponding to \(\omega_{\mathrm{p}} \ll E_{\mathrm{F}}\) are beyond current experimental reach terrestrially, they can be found in ultra- dense astrophysical objects [61, 62].  

As a critical application, we compute Coulomb pseudopotentials for the uniform electron gas (UEG) using recently developed variational diagrammatic Monte Carlo (DiagMC) method [63- 70]. These results provide precise parameterization of \(\mu^{*}\) as a function of electron density to be used in ME treatment of real materials. Our estimates of the "bare" pseudopotential, obtained by first computing the quasiparticle scattering amplitude at the Fermi surface and then renormalizing it via the Cooper/Tolmachev logarithm, are significantly larger than estimates based on static screening or RPA in the moderate- density regime, bridging a crucial gap between theory and experiment. We also compute the quasiparticle e- ph vertex for the UEG, finding that DFPT yields remarkably accurate electron- phonon coupling values for simple metals.   

By combining these advances with calculations of the precursory Cooper flow (PCF) of the anomalous vertex function in the normal state [25], we propose an ab initio workflow, capable of predicting low- temperature SC and quantum phase transition points well beyond the reach of conventional methods. With this approach, we revisited the problem of superconducting \(T_{c}\) in various simple metals under ambient and high- pressure conditions. Our method yields orders- of- magnitude improvements in predicting \(T_{c}\) for sub- Kelvin superconductors compared to previous estimates based on a phenomenological \(\mu^{*}\) . We find that Mg and Na are close to a normal- SC quantum phase transition, offering an opportunity to study quantum critical scaling below 10K. We also predict that Al will undergo a transition to the normal state under pressure exceeding 60GPa. In the UEG context, this work establishes a complete and controlled first- principles framework for understanding the interplay between the electron correlations and e- ph interactions in SC. If rigorously followed in simulations of real materials, it will radically improve our ability to design next- generation superconducting materials.  

The rest of the paper is organized as follows. In Sec. II, we establish the effective field theory for the coupled electron- phonon system and introduce the Bethe- Salpeter equation (BSE) formalism used to detect superconducting instabilities. Sec. III provides the microscopic derivation of the downfolding approximation, rigorously integrating out high- energy degrees of freedom to establish the exact relations between the quasiparticle vertex functions and the Coulomb pseudopotential \(\mu^{*}\) and the effective coupling \(\lambda\) . Building on this framework, Sec. IV focuses on the quantitative determination of \(\mu^{*}\) using high- order Variational Diagrammatic Monte Carlo (VDiagMC) simulations of the Uniform Electron Gas. In Sec. V, we address the effective coupling \(\lambda\) by benchmarking standard Density Functional Perturbation Theory (DFPT) against our many- body theory within the UEG model, thereby establishing the precise correspondence between the DFPT- derived interaction and the effective coupling in our theory. Finally, in Sec. VI, we combine these ab initio inputs within the precursory Cooper flow framework to compute \(T_{c}\) for a series of elemental metals, resolving discrepancies in lithium and predicting quantum critical behavior in magnesium and sodium. Appendices contain technical details of the calculations.



## II. THE MODEL AND BASIC RELATIONS  

### A. Electron-Phonon Problem  

Our goal is to address electron- phonon SC in crystals using effective field theory (EFT) [71] derived on the assumption that the electron mass \(m\) is much less than an ionic mass \(M\) . The mass difference has three essential consequences: the typical phonon frequency \(\omega_{\mathrm{D}}\) is suppressed relative to \(E_{\mathrm{F}}\) by a factor of \((m / M)^{1 / 2}\) , ensuring that electrons adiabatically adjust to the ionic motion; the momentum transferred by an electron to an ion in collision is very small, justifying a linearization of the electron- ion coupling; and the separation of spatial and temporal scales of electronic and phononic physics justifies a controlled EFT treatment- in particular, once properties of the pure Coulomb system (no phonons) are established at energies greater than \(\omega_{\mathrm{D}}\) , further corrections to the e- ph vertex are suppressed by \((m / M)^{1 / 2}\) allowing for simple perturbative analysis of the low- energy theory.  

For transparency, we present the formalism for systems with a near- spherical Fermi surface confined to a single Brillouin zone (e.g., alkali metals) such that all low- energy processes can be parameterized by the crystal momentum \(\mathbf{k}\) . This formalism also applies to simple multivalent metals (e.g., Mg, Al): while their Fermi surfaces span multiple Brillouin zones, an approximate rotation symmetry in the extended zone scheme is still present due to weak ionic potential and Umklapp scattering. For these systems, the total momentum \(\mathbf{K} = \mathbf{k} + \mathbf{G}_{m}\) (where \(\mathbf{G}_{m}\) is a reciprocal lattice vector) is approximately conserved and can be used in place of the crystal momentum \(\mathbf{k}\) . This correspondence simplifies the presentation while retaining physical clarity. For materials with strong Umklapp scattering and lattice potentials, we provide a generalized \((\mathbf{k}, \mathbf{G})\) formalism in Appendix A, ensuring broad applicability without obscuring the core physics.  

By keeping terms up to quadratic order in ionic displacements (see Appendix A), we obtain an effective action accurate up to \(O(\sqrt{m / M})\) corrections:  

\[S = S_{t x e}[\bar{\psi},\psi ] + S_{\mathrm{ph}}[u] + S_{\mathrm{e - ph}}[\bar{\psi},\psi ,u] + S_{\mathrm{CT}}[u] + O\left(\sqrt{\frac{m}{M}}\right), \quad (1)\]  

where \(\psi\) , \(\bar{\psi}\) are Grassmann fields for electrons, and \(u\) is the ionic displacement field rescaled by \(\sqrt{M}\) (this standard procedure applies to any number of ions in the unit cell). Here, \(S_{\mathrm{e}}\) stands for full many- electron action without any approximations. We distinguish our theory from the conventional DFT approach, which replaces \(S_{\mathrm{e}}\) with a non- interacting reference Hamiltonian governed by an approximate exchange- correlation potential [72, 73]. The DFT approach does not capture the dynamical effects of electron- electron interactions.  

For simplicity we take the e- ph coupling \(S_{\mathrm{e - ph}}\) to have  

the density- displacement form  

\[S_{\mathrm{e - ph}} = \sum_{\kappa}\int_{\mathbf{q}\nu}g_{\kappa}^{(\mathrm{o})}(\mathbf{q})n_{\mathbf{q}\nu}u_{\kappa \mathbf{q}\nu}, \quad (2)\]  

summed over phonon branches \(\kappa\) , momenta \(\mathbf{q}\) in the Brillouin zone, and Matsubara frequencies \(\nu\) . This approximation captures the coupling of the electronic density to longitudinal phonon modes and is adequate for the simple case of nearly free electron materials with electronic eigenstates that are close to plane waves; the generalization to more complicated situations is straightforward but notationally cumbersome and will not be considered here.  

\(S_{\mathrm{ph}}\) describes phonons with physical dispersion \(\omega_{\kappa \mathbf{q}}\) ,  

\[S_{\mathrm{ph}} = \frac{1}{2}\sum_{\kappa}\int_{\mathbf{q}\nu}D_{\kappa \mathbf{q}\nu}^{-1}|u_{\kappa \mathbf{q}\nu}|^{2}, \quad (3)\]  

where \(D_{\kappa \mathbf{q}\nu} = - 1 / (\nu^{2} + \omega_{\kappa \mathbf{q}}^{2})\) is the phonon propagator. The physical dispersion \(\omega_{\kappa \mathbf{q}}\) is characterized by the Debye frequency, \(\omega_{\mathrm{D}}\) . In the case we consider, the Debye frequency is assumed to be much smaller than the Fermi energy, \(E_{\mathrm{F}}\) , i.e. \(\omega_{\mathrm{D}} \ll E_{\mathrm{F}}\) . This separation of energy scales will be the basis for the approximations made later.  

Defining \(S_{\mathrm{ph}}\) in terms of the physical (experimentally measured) dispersion \(\omega_{\kappa \mathbf{q}}\) is convenient, because within the Migdal approximation \(\omega_{\kappa \mathbf{q}}\) is determined by the ion masses and interionic forces defined from the change in total energy with respect to static displacements of ions from their equilibrium positions; the changes in energy may in many cases be accurately computed using known ab- initio methods. However, this choice means that in the theoretical analysis one must take care of double- counting: since the renormalized phonon spectrum already includes screening effects from the static limit of the electron polarization. When treating the e- ph coupling \(S_{\mathrm{ph}}\) perturbatively the static limit of the electronic polarization contribution to the phonon spectrum should be excluded. Formally, this is done by introducing a counterterm \(S_{\mathrm{CT}}\) , which subtracts the corresponding screening contributions. By construction, it is given by the zero frequency limit of the electron charge susceptibility \(\chi_{\mathbf{q}}^{\mathrm{e}}\) , which quantifies how electrons respond to density fluctuations:  

\[S_{\mathrm{CT}} = -\frac{1}{2}\sum_{\kappa}\int_{\mathbf{q}\nu}\left(g_{\kappa \mathbf{q}}^{(0)}\right)^{2}\chi_{\mathbf{q}}^{\mathrm{e}}|u_{\kappa \mathbf{q}\nu}|^{2}. \quad (4)\]  

This formulation ensures that the phonon propagator retains its physical properties and no double- counting takes place when performing perturbative expansion in terms of the e- ph interaction.  

### B. Bethe-Salpeter Equation (BSE)  

The standard ME formalism probes superconductivity via an analysis of equations governing the normal and


![](images/4_0.jpg)

<center>FIG. 1. Normal component of the electron self-energy approximated by the self-consistent Fock diagram with the phonon-mediated e-e interaction \(W^{ph}\) . According to Migdal's theorem, higher-order vertex corrections based on \(W^{ph}\) are suppressed by \(O(\omega_{\mathrm{D}} / E_{\mathrm{F}})\) . </center>  

![](images/4_1.jpg)

<center>FIG. 2. Diagrammatic representation of the phonon-mediated e-e interaction, \(W^{\mathrm{ph}}\) , composed of the phonon propagator, \(D\) , bare coupling \(g^{(0)}\) , vertex function \(\Gamma_5^e\) , and the dielectric function \(\epsilon_{\mathrm{q}\nu}\) . The last two are combined to form the screened electron-phonon coupling. </center>  

anomalous parts of the electron self energy. The normal self- energy, diagrammatically depicted in Fig. 1, is  

\[\Sigma_{\mathbf{k}\omega} = \Sigma_{\mathbf{k}\omega}^{\mathrm{e}} + \int_{\mathbf{q}\nu}G_{\mathbf{k} + \mathbf{q}\omega -\nu}W_{\mathbf{k}\omega ,\mathbf{k} + \mathbf{q}\omega +\nu ;\mathbf{q}\nu}^{\mathrm{ph}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}}\right). \quad (5)\]  

It consists of two terms with the first one, \(\Sigma_{\mathbf{k}\omega}^{\mathrm{e}}\) , coming entirely from the non- perturbative Coulomb interactions. The second term has the structure of the self- consistent Fock diagram based on the dressed phonon- mediated interaction \(W^{\mathrm{ph}}\) shown in Fig. 2. By construction, \(W^{\mathrm{ph}}\) incorporates all non- perturbative Coulomb effects such as screening and vertex corrections. Migdal's theorem ensures that vertex corrections higher- order in \(W^{\mathrm{ph}}\) are suppressed by \(\omega_{\mathrm{D}} / E_{\mathrm{F}}\) , justifying truncation at this level of accuracy [10]. Similarly, the anomalous (superconducting) self- energy has a Coulomb contribution, \(\Sigma_{\mathbf{k}\omega}^{\mathrm{a,e}}\) and a self- consistent "Fock- type" contribution based on  

![](images/4_2.jpg)

<center>FIG. 3. Self-consistent Bethe-Salpeter equation for the anomalous vertex \(\Lambda (\mathbf{k}, -\mathbf{k}; \mathbf{q} = 0)\) in momentum space, where \(\mathbf{k}\) and \(-\mathbf{k}\) are the momenta of the outgoing electrons. The total momentum \(\mathbf{q}\) is set to zero, as this corresponds to the leading Cooper instability in our case. The kernel consists of the particle-particle irreducible 4-point vertex \(\tilde{\Gamma}^{\mathrm{e}}\) , which is a purely electronic contribution, and the phonon-mediated interaction \(W^{\mathrm{ph}}\) described in Fig. 2; higher-order vertex corrections are small according to Migdal's theorem. </center>  

the phonon- mediated interaction  

\[\Sigma_{\mathbf{k}\omega}^{\mathrm{a}} = \Sigma_{\mathbf{k}\omega}^{\mathrm{a,e}} + \int_{\mathbf{q}\nu}F_{\mathbf{k} + \mathbf{q},\omega -\nu}W_{\mathbf{k}\omega , - \mathbf{k} - \omega ;\mathbf{q}\nu}^{\mathrm{ph}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}}\right). \quad (6)\]  

The equation for the anomalous self energy involves the anomalous (Gorkov) propagator, \(F_{\mathbf{k}\omega} = \langle \psi_{\mathbf{k},\omega}^{\dagger}\psi_{-\mathbf{k},-\omega}^{\dagger}\rangle\) , which encodes precursor Cooper pairing fluctuations.  

These two equations are in effect the standard Migdal- Eliashberg equations, expressed in the current notations. The transition temperature is typically found by linearizing the second equation. Analysis even of the linearized equation can be challenging for low \(T_{c}\) superconductors where a dense computational mesh is required and for strong coupling situations, where extrapolation of the leading eigenvalues of the linearized gap equation is not straightforward. If the goal is limited to prediction of \(T_{c}\) , then following Ref. [25], it is more efficient to probe SC from the high- temperature normal state ( \(T \gg T_{c}\) ) by solving Bethe- Salpeter equation (BSE) for the anomalous vertex function defined from the linear response of the anomalous self energy to an applied pairing field. Here, we apply this approach in the context of the electron- phonon SC by considering response to an infinitesimal symmetry- breaking pair- field term ( \(\eta^{\mathrm{a}} \to 0\) ):  

\[S_{e}[\bar{\psi},\psi ;\eta^{\mathrm{a}}] \equiv S_{e}[\bar{\psi},\psi ] + \int_{\mathbf{k}\omega}[\eta^{\mathrm{a}}\bar{\psi}_{\mathbf{k},\omega}^{\dagger}\bar{\psi}_{-\mathbf{k},-\omega}^{\dagger} + \mathrm{H.c.}]. \quad (7)\]  

This symmetry- breaking term induces an anomalous (Gorkov) propagator, \(F_{\mathbf{k}\omega} = \langle \psi_{\mathbf{k},\omega}^{\dagger}\psi_{-\mathbf{k},-\omega}^{\dagger}\rangle \propto \eta^{\mathrm{a}}\) , which encodes precursor Cooper pairing fluctuations. The normal propagator, \(G_{\mathbf{k}\omega}\) , remains unperturbed to leading order in \(\eta^{\mathrm{a}}\) . The linear response of the electron self- energy to \(\eta^{\mathrm{a}}\) is given by the anomalous vertex, \(\Lambda_{\mathbf{k}\omega}\) , for details, see Appendix B, which encodes the diverging Cooper susceptibility, if any, and obeys the Bethe- Salpeter equation (BSE),  

\[\Lambda_{\mathbf{k}\omega} = \eta_{\mathbf{k}\omega} + \int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}G_{\mathbf{k}^{\prime}\omega^{\prime}}G_{-\mathbf{k}^{\prime},-\omega^{\prime}}\Lambda_{\mathbf{k}^{\prime}\omega^{\prime}}. \quad (8)\]  

Here we have written \(\eta^{\mathrm{a}} = \bar{\eta}\eta_{k\omega}\) with \(\bar{\eta}\) an infinitesimal. The source term \(\eta_{k\omega}\) is a function of momentum and frequency defining the symmetry channel and the range over which pairing is probed. Since the critical temperature is defined by the singularity of the homogeneous BSE and is independent of the source profile (provided non- orthogonality to the critical mode) we will in many cases set \(\eta_{k\omega} = 1\) .  

The BSE kernel \(\tilde{\Gamma} = \frac{\delta\Sigma^{\mathrm{a}}}{\delta F}\) is the particle- particle irreducible four- point vertex function with contributions from both the e- e interactions and the e- ph coupling. The subscript notation for \(\tilde{\Gamma}\) is a compact representation of the incoming and outgoing Cooper pair momentum- frequency indexes \((\mathbf{k}, \omega ; -\mathbf{k}, -\omega)\) and \((\mathbf{k}^{\prime}, \omega^{\prime}; -\mathbf{k}^{\prime}, -\omega^{\prime})\) , respectively.  

Migdal's theorem allows one to write the kernel as the sum of purely electronic particle- particle irreducible



vertex \((\tilde{\Gamma}^{\mathrm{e}})\) and phonon- mediated interaction \((W^{\mathrm{ph}})\) , as shown in Fig. 3,  

\[\tilde{\Gamma} = \tilde{\Gamma}^{\mathrm{e}} + W^{\mathrm{ph}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}}\right). \quad (9)\]  

By combining the BSE with the Dyson equation for \(G\) and evaluation of the effective phonon- mediated coupling \(W^{\mathrm{ph}}\) one obtains a closed set of self- consistent equations to be solved in the normal state.  

### C. Precursory Cooper Flow  

The anomalous vertex function, \(\Lambda_{\mathrm{k}\omega}\) , is used not only to predict \(T_{\mathrm{c}}\) but also to study pairing fluctuations in the normal state and the critical gap function \(\Delta_{\mathrm{k}\omega}\) . We denote the low- frequency limit of \(\Lambda_{\mathrm{k}\omega}\) averaged over the Fermi surface as \(\Lambda_0\) . It obeys a universal scaling relation known as the precursory Cooper flow (PCF) [25]:  

\[\Lambda_{0} = \frac{1}{1 + g\ln(\omega_{\Lambda} / T)} +\mathcal{O}(T), \quad (10)\]  

where both the dimensionless coupling constant \(g\) and high- energy cutoff \(\omega_{\Lambda}\) depend on the microscopic details of the system. For negative values of \(g\) , the vertex function diverges at \(T_{\mathrm{c}} = \omega_{\Lambda}e^{1 / g}\) , signaling the onset of Cooper instability. By computing \(\Lambda_0\) at several low- temperature points above \(T_{\mathrm{c}}\) and extrapolating the data according to the PCF scaling, one can accurately predict \(T_{\mathrm{c}}\) without the need to perform computationally challenging calculations at \(T_{\mathrm{c}}\) . This is particularly advantageous when complex frequency- dependent interactions prevent standard linearized ME solutions from extrapolating reliably from higher temperatures [25, 74], which would otherwise force one to solve the equations directly at the critical point.  

As the temperature approaches \(T_{\mathrm{c}}\) from above, BSE solutions provide direct access to the superconducting gap function, \(\Delta_{\mathrm{k}\omega}\) . In this limit, the diverging anomalous vertex \(\Lambda_{\mathrm{k}\omega}\) is proportional to the gap function, with \(\Lambda_{\mathrm{k}\omega} \sim \Delta_{\mathrm{k}\omega} / (T - T_{\mathrm{c}})\) . Substituting this scaling into Eq. (8), we observe that the diverging prefactor \((T - T_{\mathrm{c}})^{- 1}\) cancels out and BSE reduces to  

\[\Delta_{\mathrm{k}\omega} = \int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}G_{\mathbf{k}^{\prime}\omega^{\prime}}G_{-\mathbf{k}^{\prime},-\omega^{\prime}}\Delta_{\mathbf{k}^{\prime}\omega^{\prime}}, \quad (11)\]  

which is identical to the linearized Migdal- Eliashberg (ME) gap equation. What favorably distinguishes PCF from the traditional approach based on the temperature dependence of the largest eigenvalue \(h(T)\) in  

\[h(T)\Delta_{\mathrm{k}\omega} = \int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}G_{\mathbf{k}^{\prime}\omega^{\prime}}G_{-\mathbf{k}^{\prime},-\omega^{\prime}}\Delta_{\mathbf{k}^{\prime}\omega^{\prime}}, \quad (12)\]  

is the precise scaling law (10). In a system with strong repulsive interactions, there is no simple way to reliably extrapolate \(h(T)\) towards low temperature [74].  

## III. DOWNFOLDING THE BSE  

### A. Theoretical Overview  

Eq. 8, Fig. 3 for the pairing kernel is exact but not in general tractable. The fundamental difficulty is that the BSE kernel, i.e., the two- particle irreducible vertex function \(\tilde{\Gamma}\) , is not known in the general case. Widely used approximations, such as the RPA, neglect non- perturbative vertex corrections and are, thus, unreliable beyond the weakly interacting regime. Further, the full momentum and frequency dependence of \(\tilde{\Gamma}\) renders a solution of the BSE computationally intractable in the general case. Historically, these limitations have restricted applications of the BSE to simplified models and necessitated severe approximations.  

Eliashberg [11, 12] recognized that a discussion of superconductivity in conventional materials should focus on interactions near the Fermi surface and proposed a "downfolding" approximation based on effective interactions between low- energy electronic states that led to a more tractable frequency- only equation for the superconducting gap function. However, as discussed extensively above, to date the parameters (especially those relating to the electron- electron interactions) in the downfolded theory have typically been treated in ways that are phenomenological or theoretically unjustified.  

The Wilsonian renormalization scheme is a formally rigorous method for downfolding an interacting electron problem to obtain a low energy theory [19, 75]. It formalizes Landau Fermi liquid theory by partitioning electron and phonon propagators into high- energy and low- energy contributions separated by an intermediate energy scale \(\omega_{\mathrm{D}} \ll \omega_{\mathrm{c}} \ll E_{\mathrm{F}}\) . The high- energy contributions are then absorbed into effective couplings that govern the low- energy theory for the quasiparticle pair- field. However, a crucial complication arises in the standard applications of this scheme to the electron liquid: the low- energy electrons, which are essential for dynamic screening of the long- range Coulomb interaction, are absent in the renormalization of the effective coupling because the separation is constructed in the particle- hole channel. As a result, the Coulomb interaction remains unscreened below the energy scale \(\omega_{\mathrm{c}}\) , leading to a singularity in the effective coupling that is awkward to handle.  

In this work, we introduce the energy scale separation in the two- electron channel rather than in the single- electron or electron- hole channels. This approach preserves key features of the screening while avoiding the subtle issues encountered in previous attempts [19, 75]. We decompose the pair propagator into low- energy (IR) coherent and high- energy (UV) incoherent components, separated at the energy scale \(\omega_{\mathrm{c}}\) ,  

\[G_{\mathbf{k},\omega}G_{-\mathbf{k},-\omega} = \Pi_{BCS} + \phi_{\mathbf{k}\omega}, \quad (13)\]



with  

\[\Pi_{BCS} = \frac{(z^{\mathrm{e}})^2}{\left(\frac{\omega}{z_{\mathrm{w}}^{\mathrm{ph}}}\right)^2 + \epsilon_{\mathbf{k}}^2}\Theta (\omega_{\mathrm{c}} - |\epsilon_{\mathbf{k}}|) \quad (14)\]  

Here, \(\mathbf{k},\omega\) is the momentum/frequency of the pair- field, \(\phi\) denotes the incoherent contribution, an intrinsic property of the electron liquid with phonon contributions \(\mathcal{O}\left(\frac{\omega_D}{E_F}\right)\) which remains regular across the Fermi surface at low temperature. We have anticipated subsequent results by writing the coherent contribution in terms of \(z^{\mathrm{e}}\) , the quasiparticle weight arising from e- e interactions which is independent of frequency and momentum on the scales of interest, and \(z_{\mathrm{w}}^{\mathrm{ph}}\) , the frequency- dependent quasiparticle weight from e- ph interaction. \(\epsilon_{\mathbf{k}}\) is the linearized quasiparticle dispersion renormalized by e- e interactions. Formally, the effective mass renormalization \(m^{*}\) is fully incorporated into \(\epsilon_{\mathbf{k}}\) and the subsequent effective density of states \(N_{F}^{*}\) . Although established QMC and DiagMC results [76, 77] indicate that \(m^{*}\) deviates only slightly from the bare mass in the density range of interest, we retain this distinction to separate mass renormalization from the spectral weight reduction \(z^{\mathrm{e}}\) .  

In addition to the separation of the pair propagator \(\Pi\) into coherent and incoherent parts, a consistent low- energy theory requires a corresponding treatment of the vertex \(\tilde{\Gamma}\) . Formally, following Migdal's theorem, the vertex \(\tilde{\Gamma}\) can be decomposed into a phonon- mediated attraction \(W^{\mathrm{ph}}\) and an electron- electron (e- e) interaction \(\tilde{\Gamma}^{\mathrm{e}}\) [see Eq. (9)]. However, this decomposition of the kernel does not automatically guarantee the separability of the resulting Bethe- Salpeter equation. Specifically, the existence of cross terms of the form \(\tilde{\Gamma}^{\mathrm{e}}\cdot \phi \cdot W^{\mathrm{ph}}\) in the renormalization process could potentially couple the two channels, thereby invalidating the assumption of a universal, independent e- e pseudopotential in the downfolded theory.  

In metallic systems, the impact of these cross terms is particularly critical because \(\tilde{\Gamma}^{\mathrm{e}}\) must account for long- range, dynamically screened Coulomb interactions. To quantify this effect, we utilize the fact that in the limit of vanishing momentum transfer and low frequency, the dynamical interaction rigorously follows the asymptotic form:  

\[W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{\mathrm{s}} = \frac{4\pi e^{2}}{|\mathbf{k} - \mathbf{k}^{\prime}|^{2}}\frac{(\omega - \omega^{\prime})^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathrm{p}}^{2}}. \quad (15)\]  

This expression captures the exact infrared behavior of the interaction. While extending this asymptotic form to finite momenta and frequencies (effectively treating it as a plasmon- pole model) tends to overestimate the range of the interaction in phase space, it provides a strictly conservative estimate for the cross terms. As detailed in Appendix C3, even with this overestimation, the resulting cross terms are suppressed by \(\omega_{c}^{2} / \omega_{\mathrm{p}}^{2}\) , justifying the low- energy separation. Consequently, provided the  

plasmon frequency \(\omega_{\mathrm{p}}\) is sufficiently high compared to the cutoff \(\omega_{\mathrm{c}}\) , the interaction channels remain effectively decoupled, justifying the low- energy separation.  

We utilize this suppression to simplify the Bethe- Salpeter equation (BSE). We assume the external source \(\eta_{\omega}\) is non- zero only at low frequencies ( \(|\omega |< \omega_{\mathrm{c}}\) ) and partition the anomalous vertex \(\Lambda\) into two frequency sectors: a low- energy component \(\Lambda_{L}\) (where \(|\omega |< \omega_{\mathrm{c}}\) ) and a high- energy component \(\Lambda_{H}\) (where \(|\omega | > \omega_{\mathrm{c}}\) ). Adopting a shorthand notation where integrals are implicit and the subscripts \(L\) and \(H\) denote the respective frequency ranges, we recast Eq. 8 as:  

\[\begin{array}{l}{\Lambda_{L} = \eta_{\omega} + \tilde{\Gamma}_{LL}\Pi_{BCS}\Lambda_{L} + \tilde{\Gamma}_{LH}\phi \Lambda_{H} + O\left(\frac{\omega_{\mathrm{c}}^{2}}{\omega_{\mathrm{p}}^{2}}\right)}\\ {\Lambda_{H} = \tilde{\Gamma}_{HL}\Pi_{BCS}\Lambda_{L} + \tilde{\Gamma}_{HH}\phi \Lambda_{H} + O\left(\frac{\omega_{\mathrm{c}}^{2}}{\omega_{\mathrm{p}}^{2}}\right).} \end{array} \quad (16)\]  

By neglecting the suppressed cross terms and eliminating the high- energy sector \(\Lambda_{H}\) , we reduce the BSE to an effective description restricted to the low- energy window \(|\omega |< \omega_{\mathrm{c}}\) :  

\[\Lambda_{k\omega} = \eta_{\omega} + \sum_{k^{\prime},\omega^{\prime}}\tilde{\Gamma}_{k\omega ,k^{\prime}\omega^{\prime}}^{\omega_{\mathrm{c}}}\Pi_{BCS}(k^{\prime},\omega^{\prime})\Lambda_{k^{\prime},\omega^{\prime}}. \quad (17)\]  

The effective vertex \(\tilde{\Gamma}^{\omega_{\mathrm{c}}}\) appearing here is particle- particle irreducible only with respect to the coherent propagator \(\Pi_{BCS}\) and incorporates all high- energy renormalization effects via the recursive relation:  

\[\tilde{\Gamma}_{k\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\omega_{\mathrm{c}}} = \tilde{\Gamma}_{k\omega ;\mathbf{k}^{\prime}\omega^{\prime}} + \sum_{\mathbf{p}\nu}\tilde{\Gamma}_{k\omega ;\mathbf{p}\nu}^{\omega}\phi_{\mathbf{p}\nu}\tilde{\Gamma}_{k\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\omega_{\mathrm{c}}}. \quad (18)\]  

Combined with Migdal's theorem, we conclude that the effective coupling projected onto the low energy subspace has a separable form  

\[\tilde{\Gamma}^{\omega_{\mathrm{c}}} = U^{\mathrm{e}} + W^{\mathrm{ph}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}},\frac{\omega_{\mathrm{c}}^{2}}{\omega_{\mathrm{p}}^{2}}\right), \quad (19)\]  

where the effective e- e interaction \(U^{\mathrm{e}}\equiv \tilde{\Gamma}^{\mathrm{e}} + \tilde{\Gamma}^{\mathrm{e}}\cdot \phi \cdot \tilde{\Gamma}^{\mathrm{e}} + \ldots\) is the property of the electron liquid independent of phonon details. Although \(\tilde{\Gamma}^{\mathrm{e}}\) and \(\phi\) separately are typically not evaluated in simulations, the final result for \(U^{\mathrm{e}}\) can be expressed through the conventional full 4- point vertex function \(\Gamma^{\mathrm{e}}\) , as detailed in Appendix C3, which can be evaluated in simulations.  

Because \(W^{\mathrm{ph}}\) and \(U^{\mathrm{e}}\) as defined above are regular functions of momentum and frequency, we may now project all momenta onto the Fermi surface (in this work, we focus on the \(s\) - wave SC and isotropic Fermi surface—solely for clarity of presentation). Using the explicit form Eq. 14 of \(\Pi_{BCS}\) and integrating over the magnitude of the momentum perpendicular to the Fermi surface we obtain a low- energy effective theory for the quasiparticle pairfield, described by a frequency- only downfolded BSE:  

\[\Lambda_{\omega} = \eta_{\omega} + \pi T\sum_{|\omega^{\prime}|< \omega_{\mathrm{c}}}(\lambda_{\omega \omega^{\prime}} - \mu_{\omega_{\mathrm{c}}})\frac{z_{\omega^{\prime}}^{\mathrm{ph}}}{|\omega^{\prime}|}\Lambda_{\omega^{\prime}}, \quad (20)\]



with corrections proportional to one of the three small parameters: \(\omega_{\mathrm{D}} / E_{\mathrm{F}}\) , \(\omega_{c}^{2} / \omega_{\mathrm{p}}^{2}\) , or \(T / \omega_{c}\) . By construction, the summation over Matsubara frequencies \(\omega^{\prime}\) is limited by the cutoff, \(|\omega^{\prime}| < \omega_{c}\) . The symmetry-breaking term [see Eq. (D38) for more details] can be set to unity, \(\eta_{\omega} = 1\) , for numerical convenience without affecting \(T_{c}\) or the gap function.  

The BSE equation depends only on Fermi- surface- averaged quantities. Specifically, \(\Lambda_{\omega} = \langle \Lambda_{\mathbf{k}_{\mathrm{F}}\omega , - \mathbf{k}_{\mathrm{F}} - \omega ;0}\rangle_{\mathrm{FS}}\) represents the frequency- dependent anomalous vertex function averaged over the Fermi surface. Similarly, \(\lambda_{\omega \omega^{\prime}} \equiv - (z^{\mathrm{e}})^{2} N_{\mathrm{F}}^{*} \left\langle W_{\mathbf{k}_{\mathrm{F}} - \mathbf{k}_{\mathrm{F}}^{\prime},\omega - \omega^{\prime}}^{\mathrm{ph}} \right\rangle_{\mathbf{k}_{\mathrm{F}}\mathbf{k}_{\mathrm{F}}^{\prime}}\) is the effective phonon- mediated interaction, where \(N_{\mathrm{F}}^{*}\) is the quasiparticle density of states.  

The frequency- dependent quasiparticle weight renormalization due to e- ph interactions, \(z_{\omega}^{\mathrm{ph}}\) , is fully determined by \(\lambda\) in the same way as in the standard Eliashberg formulation:  

\[\frac{1}{z_{\omega}^{\mathrm{ph}}} = 1 + \frac{\pi T}{\omega}\sum_{\omega^{\prime}}\frac{\omega^{\prime}}{|\omega^{\prime}|}\lambda_{\omega \omega^{\prime}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}},\frac{\omega_{c}^{2}}{\omega_{\mathrm{p}}^{2}}\right). \quad (21)\]  

Remarkably—despite singular momentum dependence at the microscopic level and complex dynamic screening, the projected effective e- e interaction reduces to a pseudopotential constant \(\mu_{\omega c}\) .  

Repeating identically the derivation that lead to Eq. (11) for the gap function at the critical point, we obtain its downfolded version as  

\[\Delta_{\omega} = \pi T_{c}\sum_{|\omega^{\prime}|< \omega_{c}}(\lambda_{\omega \omega^{\prime}} - \mu^{*})\frac{z_{\omega^{\prime}}^{\mathrm{ph}}}{|\omega^{\prime}|}\Delta_{\omega^{\prime}} + O\left(\frac{\omega_{\mathrm{D}}}{E_{\mathrm{F}}},\frac{\omega_{c}^{2}}{\omega_{\mathrm{p}}^{2}}\right), \quad (22)\]  

where the notation \(\mu^{*} = \mu_{\omega_{c}}\) , \(\omega_{*} = \omega_{c}\) is used to present it in the familiar ME form. We note that in the low- frequency limit, the term \(\lambda_{\omega \omega^{\prime}} z_{\omega^{\prime}}^{\mathrm{ph}}\) reduces to \(\lambda /(1 + \lambda)\) .  

Eqs. (21) and (22) establishes the microscopic foundation for ME equation with precise definitions of the Coulomb pseudopotential and effective e- ph coupling in terms of electron/phonon propagators and vertex functions.  

### B. The pseudopotential  

\(\mu_{\omega_{c}}\) is the coherent pair propagator irreducible particle- particle coulomb interaction; it is defined with respect to an arbitrary renormalization scale \(\omega_{c}\) . Here we discuss its relation to quantities that may be calculated. We begin by noting that in a theory with only electron- electron interactions, solving Eq. 22 with \(\lambda = 0\) and \(z^{ph} = 1\) shows that at a temperature \(T\) the effective repulsion is  

\[\gamma_{T} = \frac{\mu_{\omega_{c}}}{1 + \mu_{\omega_{c}}\ln\frac{\omega_{c}}{T}}\qquad (T\ll \omega_{c}), \quad (23)\]  

where the repulsion may also be defined in terms of the Fermi- surface- averaged two- quasiparticle scattering am  

plitude  

\[\gamma_{T}\equiv z_{c}^{2}N_{\mathrm{F}}^{*}\langle \Gamma_{\mathrm{F}}^{e}(k_{F},\omega_{0};\mathbf{k}_{F}^{\prime},\omega_{0})\rangle_{\mathbf{k}_{F},\mathbf{k}_{F}^{\prime}}, \quad (24)\]  

with \(\omega_{0} = \pi T\) the smallest Matsubara frequency. As we shall see, the right hand side of Eq. 24 can be calculated.  

\(\gamma_{T}\) is a physical quantity, and is therefore independent of the (arbitrarily chosen) separation scale \(\omega_{c}\) . This independence requires that the connection between \(\mu_{\omega_{c}}\) defined at two different scales \(\omega_{c},\omega_{c}^{\prime}\) is the Bogoliubov- Tolmachev- Shirkov relation  

\[\mu_{\omega_{c}} = \frac{\mu_{\omega_{c}^{\prime}}}{1 + \mu_{\omega_{c}^{\prime}}\ln\frac{\omega_{c}^{\prime}}{\omega_{c}}}. \quad (25)\]  

As a practical matter we may therefore compute \(\gamma_{T}\) at a convenient temperature, corresponding to a convenient \(\omega_{c}\) and then scale to any desired separation scale. One physically meaningful choice is \(E_{F}\) , the physical scale below which coherent electronic quasiparticles exist. One normally interprets \(\mu_{E_{\mathrm{F}}}\) as the pseudopotential at the Fermi energy, or, equivalently, "bare"—free of Bogoliubov- Tolmachev- Shirkov renormalization—pseudopotential.  

Our results for \(\mu_{E_{\mathrm{F}}}\) in UEG as a function of \(r_{\mathrm{s}}\) are presented in Fig. 4; the corresponding numerical values are listed in Table I. We find \(\mu_{E_{\mathrm{F}}}\) to be significantly larger (by a factor of three at \(r_{\mathrm{s}} = 5\) ) compared to MA and static RPA estimates [9, 27, 38]. Even more profound is the disagreement with dynamic RPA that predicts negative \(\mu_{\omega_{c}}\) values for \(r_{\mathrm{s}} > 2\) [20- 24]. This outcome clearly demonstrates that the MA and RPA approximations are out of control at \(r_{\mathrm{s}} > 0.5\) , which one could have expected from the mere fact that at \(r_{\mathrm{s}} > 0.5\) the results of static and dynamic RPA dramatically differ from each other.  

In addition to parameterizing the value of the Coulomb pseudopotential as a function of low frequency cutoff, Eq. (25), the bare pseudopotential \(\mu_{E_{\mathrm{F}}}\) plays yet another role that is closely related to superconductivity. The low- temperature response of the normal- Fermi- liquid state to the uniform pair- creating perturbation, \(\chi_{0}\) , has the form (see, e.g., Ref. [25]) \(\chi_{0} \propto \frac{z_{c}^{2}}{m^{*}\mu_{E_{\mathrm{F}}}}\) for \(\mu_{E_{\mathrm{F}}} > 0\) , \(\omega_{D} \ll T \ll E_{\mathrm{F}},\omega_{p}\) . From our results for \(\mu_{E_{\mathrm{F}}}\) we thus conclude that \(\chi_{0}\) gets substantially suppressed with increasing \(r_{\mathrm{s}}\) .  

<table><tr><td>rs</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td></tr><tr><td>μ0.1E_F</td><td>0.172(4)</td><td>0.238(4)</td><td>0.278(6)</td><td>0.306(15)</td><td>0.328(12)</td><td>0.35(3)</td></tr><tr><td>μE_F</td><td>0.28(1)</td><td>0.53(2)</td><td>0.77(5)</td><td>1.0(2)</td><td>1.3(2)</td><td>1.8(8)</td></tr></table>  

TABLE I. VDiagMC results for the dimensionless Coulomb pseudopotential \(\mu_{\omega_{c}}\) for integer values of \(r_{\mathrm{s}}\) (see also Fig. 4). Values were computed at \(\omega_{c} = 0.1E_{\mathrm{F}}\) and rescaled to \(E_{\mathrm{F}}\) . Numbers in parentheses indicate the estimated systematic uncertainty in the last digit.


![](images/8_0.jpg)

<center>FIG. 4. Dimensionless "bare" Coulomb pseudopotential, \(\mu_{EF}\) , as a function of \(r_{\mathrm{s}}\) for the 3D UEG extracted from VDiagMC data for \(\mu_{\omega_{\mathrm{c}}}\) by inverting relation (25); the solid line represents a linear fit to the VDiagMC data. The exact VDiagMC values corresponding to these integer \(r_{\mathrm{s}}\) points are listed in Table I. At \(r_{\mathrm{s}} > 0.5\) , the VDiagMC results demonstrate a dramatic deviation from predictions of three standard approximations: static random phase approximation (RPA) \(\mu_{\mathrm{RPA - static}}\) (red dashed curve), \(\mu_{\mathrm{MA}}\) (green dashed curve) based on the Yukawa interaction with Thomas-Fermi screening momentum, and the dynamic RPA (see, e.g., Ref. [25]), \(\mu_{\mathrm{RPA - dynamic}}\) . Note perfect agreement between all curves at \(r_{\mathrm{s}} \ll 1\) . </center>  

### C. Validation of the Fermi-Surface Downfolding  

The controlled downfolding scheme relies on the condition that \(\omega_{\mathrm{c}}\) is much smaller than the characteristic energy scales of the electron Fermi liquid. In the absence of additional emergent collective excitations, the conditions \(\omega_{\mathrm{c}} / E_{\mathrm{F}} \ll 1\) and \(\omega_{\mathrm{c}} / \omega_{\mathrm{p}} \ll 1\) are the most relevant. In 3D electron gases, the ratio \(\omega_{\mathrm{c}} / \omega_{\mathrm{p}}\) scales as \(1 / \sqrt{r_{\mathrm{s}}}\) . For most metals \(r_{\mathrm{s}} \gtrsim 1\) (even in high- pressure metallic hydrogen samples where \(r_{\mathrm{s}} \approx 0.9\) ), and one can safely estimate \(\omega_{\mathrm{c}} / \omega_{\mathrm{p}} \lesssim 0.1\) , indicating the robustness of the downfolding approximation for terrestrial and laboratory metals.  

To validate this approximation for the systems under consideration, we investigate a toy model with the two- particle- irreducible vertex function, \(\bar{\Gamma}^{\mathrm{e}}\) , approximated by the dynamically screened Coulomb interaction of the uniform electron gas within the RPA, \(W_{\mathrm{RPA}} = v_{q} / (1 - v_{q}\Pi_{q\nu}^{0})\) . For the effective phonon- mediated interaction, \(W_{q\nu}^{\mathrm{ph}}\) , we consider a model form from Ref. [23]:  

\[W_{q\nu}^{\mathrm{ph}} = -\frac{g / N\mathrm{F}}{1 + (q / 2k_{\mathrm{F}})^{2}}\frac{\omega_{q}^{2}}{\nu^{2} + \omega_{q}^{2}}, \quad (26)\]  

with the phonon dispersion \(\omega_{q}^{2} = \omega_{\mathrm{D}}^{2}(q / k_{\mathrm{F}})^{2} / (1 + (q / k_{\mathrm{F}})^{2})\) and a coupling strength of \(g = 0.4\) . We consider a conventional metallic density corresponding to \(r_{\mathrm{s}} = 1.91916\) (similar to aluminum) and a small adiabatic ratio \(\omega_{\mathrm{D}} / E_{\mathrm{F}} = 0.005\) . We then solve for the critical  

![](images/8_1.jpg)

<center>FIG. 5. Comparison between the precursory Cooper flow solutions of the full and downfolded Bethe-Salpeter equations for a toy model with the two-particle-irreducible electron vertex function approximated by the Coulomb interaction screened by RPA polarization and a typical phonon-mediated interaction. The calculation is performed at moderate \(r_{\mathrm{s}} = 1.91916\) case (representative of A1) with \(T_{\mathrm{c}}^{(\mathrm{full})} / T_{\mathrm{F}} = 10^{-5.668}\) and \(T_{\mathrm{c}}^{(\mathrm{approx})} / T_{\mathrm{F}} = 10^{-5.667}\) (difference \(\sim 0.2\%\) ), confirming the validity of the downfolding approximation. </center>  

temperature \(T_{\mathrm{c}}\) using both the full, frequency- dependent BSE and the simplified, downfolded frequency- only BSE.  

The comparison, shown in Fig. 5, demonstrates excellent agreement between the two methods. The calculated critical temperatures differ by a negligible \(0.2\%\) , confirming the quantitative accuracy of the downfolding approximation for conventional metals. When the approximation is valid, both solutions follow the same universal logarithmic scaling, aligning perfectly below the Debye frequency.  

While the downfolding framework is clearly robust in this physical regime, its accuracy could be challenged in extreme cases where the separation of energy scales is less pronounced. For instance, downfolding can become questionable in systems with low electron densities where \(E_{\mathrm{F}} \sim \omega_{\mathrm{D}}\) (a regime outside the scope of this discussion), as well as in dense systems with small \(r_{\mathrm{s}}\) . This includes certain astrophysical objects, such as the interiors of white dwarfs (slowly evolving into black dwarfs). In these systems, electrons may become superconducting at sufficiently low temperatures [61, 62], and their \(r_{\mathrm{s}}\) values can be as small as 0.01. This leads to soft plasmon frequencies and potential problems with the accuracy of the downfolding approximation. Similar, and potentially more severe, problems are anticipated in two- dimensional electron gas (2DEG) systems [78], provided the Coulomb interaction is not screened by a substrate. In that case, the plasmon mode remains gapless across all density regimes, a situation that warrants further careful investigation. A detailed analysis of such exotic regimes goes beyond the scope of the present work.



## IV. COULOMB PSEUDOPOTENTIAL FROM THE FIRST PRINCIPLES  

### A. Uniform Electron Gas  

In this section, we compute the Coulomb pseudopotential for the uniform electron gas (UEG). Now \(S_{\mathrm{e}}\) in Eq. (1) describes electrons on a uniform neutralizing background:  

\[\begin{array}{l}{S_{\mathrm{UEG}} = \int_{\mathbf{k}\omega \sigma}\bar{\psi}_{\mathbf{k}\omega}^{\sigma}\left[-i\omega +\frac{\mathbf{k}^{2}}{2m} -\mu\right]\psi_{\mathbf{k}\omega}^{\sigma}}\\ {+\frac{1}{2}\int_{\mathbf{k}\omega \sigma ,\mathbf{k}^{\prime}\omega \sigma^{\prime},\mathbf{q}\nu}\bar{\psi}_{\mathbf{k}\omega}^{\sigma}\bar{\psi}_{\mathbf{k}^{\prime}\omega}^{\sigma^{\prime}}v_{\mathbf{q}}\psi_{\mathbf{k}^{\prime} - \mathbf{q},\omega^{\prime} - \nu}^{\sigma^{\prime}}\psi_{\mathbf{k} + \mathbf{q}\omega +\nu}^{\sigma^{\prime}},} \end{array} \quad (27)\]  

here \(\bar{\psi},\psi\) are Grassmann fields, \(v_{\mathbf{q}} = 4\pi e^{2} / q^{2}\) is the Coulomb potential, and \(\mu\) is the chemical potential. The strength of interaction in UEG is characterized by the dimensionless Wigner- Seitz radius \(r_{\mathrm{s}}\) , which measures the distance between electrons in units of the Bohr radius and is proportional to the ratio between the potential and kinetic energies. Below and in numerical calculations, we follow the atomic Rydberg units convention, setting \(\hbar = 2m = e^{2} / 2 = 1\) , while other quantities such as \(E_{\mathrm{F}}\) and \(k_{\mathrm{F}}\) vary with respect to \(r_{\mathrm{s}}\) .  

The UEG is a foundational model in condensed matter physics. Not only does it apply directly to simple metals with weak lattice potentials but also within local density approximation (LDA) it is used to formulate DFT. By treating inhomogeneous electron systems as locally uniform, LDA utilizes the knowledge of ground- state properties of UEG to capture complex exchange- correlation effects. The remarkable success of LDA- based DFT in describing a broad spectrum of materials highlights importance of UEG to our understanding of interacting electrons.  

Despite the relative simplicity of the UEG model (compared to real materials) precise calculation of its Coulomb pseudopotential presents a significant challenge. We are not aware of any calculation performed with controlled accuracy for \(r_{\mathrm{s}} > 1\) . The most challenging aspect is the evaluation of the four- point vertex function in the Cooper channel on the Fermi surface. In the strongly correlated regime, this quantity cannot be obtained by traditional ground- state methods such as variational and diffusion Monte Carlo [79- 81].  

In this context, the recently developed method of Variational diagrammatic Monte Carlo [63- 70] (VDiagMC) emerges as the right tool to address the problem. Unlike the majority of quantum Monte Carlo techniques, VDiagMC is based on stochastic sampling of Feynman diagrams to high order and provides direct access to the vertex function needed for evaluation of \(\mu^{*}\) . The key principle of VDiagMC is optimization of the starting point to set up the diagrammatic expansion order- by- order. As a result, one obtains accurate converged answers even beyond the weak- coupling regime.  

Within the VDiagMC framework, we treat the UEG action \(S_{\mathrm{UEG}}\) as that of the "renormalized" Yukawa Fermi gas with counter- terms. The bare chemical potential \(\mu\) and Coulomb interaction \(v\) are expressed as power series in terms of renormalized parameters: \(\mu \equiv \mu_{\mathrm{R}} + \delta \mu_{1}\xi + \delta \mu_{2}\xi^{2} + \ldots\) , \(v(\mathbf{q}) = 4\pi e^{2} / \mathbf{q}^{2} \equiv 4\pi e^{2} / (\mathbf{q}^{2} + \lambda_{\mathrm{R}}) + \delta v_{1} \cdot \xi + \delta v_{2} \cdot \xi^{2} + \ldots\) , where \(\xi\) is an auxiliary parameter used to track the expansion order; physical result corresponding to \(\xi = 1\) . Here \(\mu_{\mathrm{R}}\) is the renormalized chemical potential set to the Fermi energy in the low- temperature limit in such a way that the tree- level propagator corresponds to the physical electron density. This is achieved by requiring that counterterms \(\delta \mu_{i}\) cancel all self- energy corrections to the Fermi energy at order \(i\) . Similarly, the Coulomb interaction \(v(\mathbf{q})\) is written as Yukawa interaction, \(v_{\mathrm{R}}(\mathbf{q}) \equiv 4\pi e^{2} / (\mathbf{q}^{2} + \lambda_{\mathrm{R}})\) , and a series of counterterms \(\delta v_{i} \equiv v_{\mathrm{R}}^{i + 1} \left(\frac{\lambda_{\mathrm{R}}}{4\pi e^{2}}\right)^{i}\) . The screening parameter, \(\lambda_{\mathrm{R}}\) , is optimized to improve convergence. With these redefinitions, we perform perturbative expansions of physical quantities in powers of \(\xi\) , effectively removing Coulomb divergences and large expansion parameters and significantly improving convergence and, thus, final accuracy.  

As detailed in Ref. [82], the efficiency of VDiagMC is greatly enhanced by representing high- order Feynman diagrams of vertex functions as computational graphs. This approach leverages the structure of Dyson- Schwinger and Parquet equations to express diagrams in a compressed form with a fractal structure of tensor operations, significantly reducing computational redundancy. Notably, this computational graph representation allows for highly efficient implementation of field- theoretic renormalization schemes of the bare parameters using Taylor- mode automatic differentiation algorithms [83- 85], reducing the computational cost of evaluating the renormalized set of diagrams from exponential to sub- exponential scaling.  

Building upon these techniques, we developed a Feynman diagram compiler that generates, optimizes, and converts the renormalized diagrammatic series into a compressed computational graph across various platforms using machine learning frameworks. This enables the implementation of high- dimensional Monte Carlo integration algorithms with state- of- the- art importance sampling techniques, such as the VEGAS [86, 87] adaptive algorithm and more advanced methods employing normalizing flow neural networks [88]. Our codes support both the conventional CPU clusters and GPU platforms, allowing for scalable and efficient computations. In practice, we can reach sufficiently high expansion orders to accurately determine various quasiparticle properties, including density, spin susceptibility, and effective mass. This combination of computational graph representation, Taylor- mode automatic differentiation, and modern machine learning frameworks provides a robust and efficient AI Tech Stack for quantum field theory.


![](images/10_0.jpg)

<center>FIG. 6. Diagrammatic contributions to the 4-point vertex at the first and second order. The Coulomb interaction is re-expanded starting from Yukawa interaction with the screening parameter \(\lambda_{\mathrm{R}}\) , resulting in a power series of counterterms based on \(\lambda_{\mathrm{R}}\) (see text). </center>  

### B. Coulomb Pseudopotential: Homotopic expansion  

With VDiagMC we construct and compute high- order power series for \(\mu_{\omega_{c}}\) for a certain computationally optimal value of \(\omega_{c}\) . The calculation starts with evaluation of the self- energy and four- point vertex functions within the renormalized UEG approach described above. Subsequently, these quantities are used to extract the quasiparticle residue, \(z^{\mathrm{e}}(\xi)\) , effective mass, \(m_{e}^{*}(\xi)\) , and the two- electron scattering amplitude, \(\Gamma^{\mathrm{e}}(\xi)\) , as power series in \(\xi\) . Finally, we combine the results to obtain the power series for \(\gamma_{T}\) ,  

\[\gamma_{T}(\xi)\equiv [z^{\mathrm{e}}(\xi)]^{2}\frac{m_{e}^{*}(\xi)}{m} N_{\mathrm{F}}\Gamma^{\mathrm{e}}(\xi)\equiv \gamma_{T}^{(0)} + \gamma_{T}^{(1)}\xi +\gamma_{T}^{(2)}\xi^{2} + \dots \quad (28)\]  

At low temperature, the convergence of the series at the physical value \(\xi = 1\) becomes problematic due to the \((\ln T)^{N}\) scaling of the \(N\) - th order term arising from nested particle- particle bubbles in the diagrammatic expansion. The solution to the convergence problem comes with a homotopic trick (cf. Ref. [89]). Assuming analyticity of \(\gamma_{T}(\xi)\) as a function of \(\xi\) , we want to construct a matching temperature- independent analytic function \(\mu_{\omega_{c}}(\xi)\) such that, on the one hand, it could be analytically expressed in terms of \(\gamma_{T}(\xi)\) and, on the other hand,  

would feature the homotopic requirement that \(\mu_{\omega_{c}}(\xi = 1)\) be equal to the value of \(\mu_{\omega_{c}}\) defined by Eq. (23). The series (28) will then be readily converted into the homotopic expansion  

\[\mu_{\omega_{c}}(\xi) = \mu_{\omega_{c}}^{(0)} + \mu_{\omega_{c}}^{(1)}\xi +\mu_{\omega_{c}}^{(2)}\xi^{2} + \dots , \quad (29)\]  

with temperature- independent coefficients, thereby providing a natural cure for the low- \(T\) convergence problem.  

The guiding principle for constructing the desired homotopy is the above- mentioned \((\ln T)^{N}\) scaling of the \(N\) - th order term of the expansion (29). The relation between \(\mu_{\omega_{c}}(\xi)\) and \(\gamma_{T}(\xi)\) has to generate corresponding counterterms. This suggests that we define  

\[\mu_{\omega_{c}}(\xi)\equiv \frac{\gamma_{T}(\xi)}{1 - \gamma_{T}(\xi)\ln(\omega_{c} / T)}. \quad (30)\]  

Expansion in powers of \(\xi\) then yields \(\mu_{\omega_{c}}^{(0)} = \gamma_{T}^{(0)}\) , \(\mu_{\omega_{c}}^{(1)} = \gamma_{T}^{(1)} + [\gamma_{T}^{(0)}]^{2}\ln (\omega_{c} / T)\) , etc.  

The low- temperature behavior of the partial sums of the series (28) at \(\xi = 1\) is shown in Fig. 7 (left panel). It reveals a logarithmic divergence below \(0.01E_{F}\) . In the right panel of Fig. 7, we present results for partial sums of the series (29) at \(\xi = 1\) (after incorporating the frequency cutoff shift induced by mass renormalization, see Appendix E 2 c for details). As anticipated, the \(\mu_{\omega_{c}}\) series does not exhibit terms with divergent behavior as \(T \to 0\) and quickly converges thus allowing us to reliably extract the value of \(\mu_{E_{F}}\) .  

The mathematical justification for this resummation protocol, including the underlying assumptions regarding analyticity and the details of the conformal map technique, is provided in Appendix E 2 d.  

## V. ELECTRON-PHONON COUPLING FROM BAND THEORY  

Accurate determination of the phonon- mediated electron- electron attraction quantified by the dimensionless coupling constant \(\lambda\) is fundamental to understanding and predicting phonon- mediated SC. Current theories of conventional superconductivity are based on defining electron- phonon coupling by using density functional theory to estimate the response of the electronic states to changes in atomic positions. This response is efficiently implemented in the density functional perturbation theory (DFPT) computational method [15, 16, 41, 90]. Currently, DFPT underlies most ab initio predictions of conventional superconductivity, yet its accuracy in correlated systems remains untested. Moreover, precise benchmarks help establish semi- phenomenological pathways for systematically correcting DFPT results, potentially extending its applicability to strongly correlated superconductors. In this section we address the fundamental question: under what conditions and with what accuracy does the EFT framework agree with the results of DFPT [15, 16, 41, 90] ?


![](images/11_0.jpg)

<center>FIG. 7. Temperature dependence of the partial sums of the series for \(\gamma_{T}\) (left panel) and corresponding results for Coulomb pseudopotential \(\mu_{\omega_{c}}\) (right panel), for a given energy scale separation parameter \(\omega_{c} = 0.1E_{\mathrm{F}}\) , \(r_{\mathrm{s}} = 1\) and \(\lambda_{\mathrm{R}} = 3.5k_{\mathrm{F}}^{2}\) . Temperature dependence of \(\gamma_{T}\) is dominated by the logarithmic divergence characteristic of the Cooper channel, with contributions at order \(N\) being proportional to \([\ln (E_{\mathrm{F}} / T)]^{N}\) . In contrast, \(N\) -th order results for \(\mu_{\omega_{c}}\) saturate to a constant at low temperature. The renormalized series for \(\mu_{\omega_{c}}\) appear to converge to a well-defined value in the \(T \to 0\) limit, thereby enabling reliable estimation of \(\mu_{E_{F}}\) . </center>  

Within the downfolded ME framework, \(\lambda\) is defined by the Fermi- surface average of the square of the ratio of the physical electron- phonon coupling \(g_{\kappa}(k,q)\) and the physical phonon frequency \(\omega_{\kappa ,q}\) following combination (below \(|\mathbf{k}| = k_{F}\) , \(|\mathbf{k}'| = |\mathbf{k} + \mathbf{q}| = k_{F}\) ),  

\[\lambda = N_{\mathrm{F}}\sum_{\kappa}\left\langle \frac{g_{\kappa}^{2}(\mathbf{k},\mathbf{q})}{\omega_{\kappa,\mathbf{q}}^{2}}\right\rangle_{\mathrm{FS}}. \quad (31)\]  

Note that the physical coupling is corrected from the bare coupling \(g_{\kappa \mathbf{q}}^{0}\) by electronic screening parameterized by the dielectric function \(\epsilon_{q}\) and vertex corrections \(\Gamma_{3}^{e}\) , as well as the quasiparticle residue \(z^{e}\) :  

\[g_{\kappa}(\mathbf{k},\mathbf{q})\equiv g_{\kappa \mathbf{q}}^{(0)}\frac{z^{e}}{\epsilon_{\mathbf{q}}}\Gamma_{3}^{e}(\mathbf{k},\mathbf{q}). \quad (32)\]  

Here, the combination \(z^{e}\Gamma_{3}^{e}(\mathbf{k},\mathbf{q})\) can be interpreted as the quasiparticle vertex correction. From now on in the main text we omit the phonon branch and reciprocal lattice vector indexes for simplicity of presentation; a complete description is presented in the Appendix A 3.  

In the small \(\mathbf{q}\) limit, the bare coupling \(g_{\mathbf{q}}^{(0)}\) associated with longitudinal fluctuations diverges as \(qv_{q}\) , whereas the coupling to transverse modes is generally regular and vanishes in the free- electron limit, becoming non- zero only when non- zero reciprocal lattice vectors are considered.  

Regardless of this asymptotic behavior, the bare interaction is screened and renormalized by the electronic response over the full kinematic range relevant to superconductivity. Given that \(\mathbf{k}\) and \(\mathbf{k} + \mathbf{q}\) both reside on the Fermi surface, the typical momentum transfer in Eq. (31) is not small, covering \(|\mathbf{q}| \in (0, 2k_{\mathrm{F}})\) . Therefore, one cannot rely on the properties of the long- wavelength limit when evaluating the effective interaction strength. In general, \(g\) depends on both incoming and outgoing momenta.  

In the framework of DFPT, the effective electron- phonon coupling is obtained by considering the linear response of the Kohn- Sham (KS) potential to ionic displacement, \(\delta V_{\mathbf{q}}^{\mathrm{KS}} = \delta V_{\mathbf{q}}^{\mathrm{ion}} + v_{\mathbf{q}}\delta n_{\mathbf{q}} + f_{\mathrm{xc}}\delta n_{\mathbf{q}}\) . This expression sums the contributions from the change in ionic potential, the electrostatic potential arising from the electron density distortion, and the exchange- correlation potential \(f_{\mathrm{xc}}\) (within LDA for simplicity). Using the linear density response \(\delta n_{\mathbf{q}} = \chi_{0}^{e}(\mathbf{q})\delta V_{\mathbf{q}}^{\mathrm{KS}}\) , where \(\chi_{0}^{e}(\mathbf{q})\) is the Lindhard function of the Kohn- Sham orbitals, we arrive at the DFPT ansatz for the electron- phonon coupling:  

\[g^{\mathrm{KS}}(\mathbf{q}) = \frac{g_{\mathbf{q}}^{(0)}}{1 - (v_{\mathbf{q}} + f_{\mathrm{xc}})\chi_{0}^{e}(\mathbf{q})}. \quad (33)\]  

The resulting quantity \(g^{\mathrm{KS}}(\mathbf{q})\) in Eq. (33) should be understood as the screened ionic potential, and therefore depends only on the transferred momentum \(\mathbf{q}\) . In standard ab initio DFPT calculations for real materials, one then converts this potential into band- resolved electron- phonon matrix elements by projecting it onto the Kohn- Sham Bloch states, \(\langle \mathbf{k} + \mathbf{q} | \delta V_{\mathbf{q}}^{\mathrm{KS}} | \mathbf{k} \rangle\) , which introduces an explicit dependence on the incoming momentum \(\mathbf{k}\) (and band indices). In the present work, however, our goal is to benchmark the screening of the underlying potential itself against the field- theoretic result. Since the EFT electron- phonon vertex is defined without any additional orbital projection, the natural DFPT object to compare with is the scalar function \(g^{\mathrm{KS}}(\mathbf{q})\) . For the homogeneous electron gas, where the Bloch projection is trivial, we can therefore match \(g^{\mathrm{KS}}(\mathbf{q})\) to the EFT vertex \(g(\mathbf{k}, \mathbf{q})\) in Eq. 32; as shown below, the residual \(\mathbf{k}\) - dependence of \(g(\mathbf{k}, \mathbf{q})\) in this regime is numerically weak and can be safely neglected.  

Using VDiagMC calculations for UEG at \(r_{s} \in [1, 5]\) we find that despite large interaction corrections to \(z^{e}\) , \(\epsilon_{\mathbf{q}}\) , and \(\Gamma_{3}^{e}(\mathbf{q})\) separately, their product involves remarkable



cancellation of interaction effects and the final result is very accurately approximated by  

\[z^{e}\frac{v_{\mathbf{q}}}{\epsilon_{\mathbf{q}}}\Gamma_{3}^{\mathrm{e}}(\mathbf{k};\mathbf{q})\approx \frac{v_{\mathbf{q}}}{1 - (v_{\mathbf{q}} + f_{xc})\chi_{0}^{\mathrm{e}}(\mathbf{q})}, \quad (34)\]  

as demonstrated in Fig. 8. Diagrammatically, the electron- electron contribution to the quasiparticle weight \(z^{\mathrm{e}}\) is effectively cancelled by the renormalization of the electron- phonon vertex described by \(\Gamma_{3}^{\mathrm{e}}\) . While this cancellation is exact in the long- wavelength limit ( \(q \to 0\) ), our numerical results demonstrate that it holds with remarkable accuracy throughout the relevant range of momentum transfers between states on the Fermi surface ( \(|q| \leq 2k_{F}\) ). This observation justifies our utilization of the DFPT- derived electron- phonon interaction within the present effective field theory framework. Thus, DFPT and EFT for UEG produce nearly identical results for UEG for all values of \(r_{\mathrm{s}} \leq 5\) :  

\[g(\mathbf{k},\mathbf{q})\approx g^{\mathrm{KS}}(\mathbf{q}). \quad (35)\]  

To obtain \(\lambda\) , the effective e- ph coupling must be combined with the physical phonon spectrum and density of states, \(N_{\mathrm{F}}\) . This is where the two methods are radically different: EFT is based on the quasiparticle density of states, while DFPT uses the band- structure density of states (bare one for UEG), \(N_{\mathrm{F}}^{(0)}\) . The two differ by the ratio of the quasiparticle mass to the electron mass. Recent high- precision calculations for UEG [70, 91] find this ratio to be very close to unity (with sub- percent accuracy at \(r_{\mathrm{s}} = 5\) ). Therefore, the two densities of states end up nearly identical despite strong correlations.  

Based on benchmark results for effective e- ph coupling and quasiparticle mass, we conclude that DFPT approximations for \(\lambda\) are fully justified in simple metals such as Li, Na, and K. However, for strongly correlated systems with complex band structure that cannot be approximated by UEG, such as semi- core electrons in transition metals, the accuracy of DFPT approximations remains an open question requiring further investigation by developing the corresponding EFT strategy. Understanding DFPT limitations and possible improvements in evaluating \(\lambda\) is crucial for accurately predicting SC properties of a wider class of materials.  

## VI. CONVENTIONAL SUPERCONDUCTORS  

We describe the ab initio flowchart illustrated in Fig. 9 to predict SC from a microscopic model within the downfolded BSE theory, detailing a systematic approach to compute the superconducting transition temperature and related properties. This framework is broadly applicable to e- ph superconductors in generic correlated materials (e.g., simple metals, transition metals, and Hubbard- type tight- binding models), provided the adiabatic approximation holds (small \(m / M\) and \(\omega_{\mathrm{D}} / E_{\mathrm{F}}\) ratio), and the plasmon mode \(\omega_{p} \sim E_{F}\) . Here we consider clean metals,  

![](images/12_0.jpg)

<center>FIG. 8. Comparison between the angle-resolved e-ph vertex correction in the uniform electron gas from variational diagrammatic Monte Carlo (points) and density functional perturbation theory (lines). The data are shown for \(z^{\mathrm{qp}}N_{\mathrm{F}}W_{\mathrm{q}}^{\mathrm{qp}}\Gamma_{3}^{\mathrm{qp}}(\mathbf{k},\mathbf{q})\) (VDiagMC data points), where \(W_{\mathrm{q}}^{\mathrm{qp}} = N_{\mathrm{F}}v_{\mathrm{q}} / \epsilon_{\mathrm{q}}\) is the dimensionless screened Coulomb interaction. </center>  

The DFPT ansatz of \(z^{\mathrm{qp}}N_{\mathrm{F}}W_{\mathrm{q}}^{\mathrm{qp}}\Gamma_{3}^{\mathrm{qp}}(\mathbf{k},\mathbf{q})\) , \(\frac{N_{\mathrm{F}}^{(0)}v_{\mathrm{q}}}{1 - (v_{\mathrm{q}} + f_{xc})\chi_{0}^{\mathrm{e}}(\mathbf{q})}\) (lines), is based on the Lindhard function, \(\chi_{0}^{\mathrm{e}}(\mathbf{q})\) , and exchange- correlation kernel in the local density approximation, \(f_{xc}\) . Excellent agreement is observed for all values of \(r_{\mathrm{s}}\) and angles \(\theta\) between the incoming \((\mathbf{k})\) and outgoing \((\mathbf{k} + \mathbf{q})\) electron momenta on the Fermi surface, except for the challenging backscattering region, \(\theta \approx \pi\) , where the diagrammatic series become sensitive to the logarithmic divergence in the Cooper channel.  

although generalization to include disorder is straightforward. The calculation proceeds along two interconnected directions: the correlated- electron part (blue boxes) and the phonon- related part (red boxes). All calculations start from the fundamental system parameters.  

The correlated- electron part focuses on computing three crucial quantities: (i) the density- density correlation function, \(\chi^{\mathrm{e}}(\mathbf{q})\) , (ii) the quasiparticle vertex correction, screened by the dielectric function, \(z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}}(\mathbf{k},\mathbf{q}) / \epsilon_{\mathrm{q}}\) , where \(\mathbf{k}\) is the incoming electron momentum, and \(\mathbf{q}\) is the momentum transfer, and (iii) the static quasiparticle e- e scattering amplitude averaged over the Fermi surface, \(z_{\mathrm{e}}^{2}N_{\mathrm{F}}^{\mathrm{e}}\langle \Gamma_{\mathrm{q}}^{\mathrm{e}}\rangle_{\mathrm{FS}}\) . The last quantity is crucial for extracting the Coulomb pseudopotential \(\mu^{*}\) . Quantities (i) and (ii) are required for determining the effective phonon- mediated attraction in the presence of strong electron correlations.  

The output of the correlated electrons flowchart, namely \(\chi^{\mathrm{e}}\) and \(z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}}\) , is fed into the phonon part of the flowchart. The effective mass density is used to compute the phonon dispersion renormalization, while \(z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}}\) accounts for screening and renormalization of e- ph interaction between the quasiparticles dressed by e- e correlations. Finally, the two flowchart parts are combined by substituting \(\lambda\) and \(\mu^{*}\) as inputs to the downfolded ME (or BSE) equation. By solving this equation one obtains \(T_{\mathrm{c}}\) , the frequency- dependent anomalous vertex correction, \(\Lambda (\omega)\) , and the frequency- dependent supercon


![](images/13_0.jpg)

<center>FIG. 9. Proposed ab initio framework for electron-phonon SC beyond the weak correlation limit. Many-electron properties (blue boxes) such as the quasiparticle density of states \(N_{F}^{*}\) , quasiparticle weight, \(z_{e}\) , density-density correlation function, as well as the three-point \((\Gamma_{3}^{*})\) and four-point \((\Gamma_{4}^{*})\) vertex functions on the Fermi surface, are computed using high-order variational Diagrammatic Monte Carlo (or any other unbiased method). These quantities are subsequently used as inputs for determining the phonon-mediated attraction (red box) and the Coulomb pseudopotential within a many-electron formalism. Specifically, \(\mu^{*}\) is deduced from the quasiparticle scattering in the Cooper-channel averaged over the Fermi surface. In radical departure from the standard ME framework, the critical temperature and gap function are calculated using the precursory Cooper flow of the anomalous vertex in the normal phase, enabling predictions of low-temperature SC and quantum phase transitions that are impossible to obtain within the conventional ME technique. </center>  

ducting gap function, \(\Delta (\omega)\) , at the critical point. This completes the ab initio procedure to predict superconducting properties from normal state calculations.  

We apply this framework to revisit e- ph SC in simple metals where properties of conduction electrons can be approximated by UEG. Existing predictions of \(T_{c}\) based on the downfolded ME theory or derived approximations, such as the McMillan or Allen- Dynes formulas, result in order- of- magnitude uncertainties for simple metals with sub- Kelvin \(T_{c}\) , depending on the choice of the phenomenological Coulomb pseudopotential [9].  

Our theory is based on two assumptions: (i) core and conduction bands are well separated by large gaps, (ii) lattice potential experienced by the conduction electrons is weak/smooth allowing us to neglect Umklapp scattering processes. Under these assumptions, it is possible to use our calculated Coulomb pseudopotential results for UEG corresponding to the material value of \(r_{s}\) . The same approach cannot be applied to materials exhibiting strong lattice potentials (e.g., Be), significant contributions from core electrons (e.g., Fe, Cu), strong spin- orbit coupling (e.g., Ta), flat- bands near the Fermi surface (e.g., Ca), or high- \(T_{c}\) metals (with \(T_{c} \gg 1K\) , e.g., Pb) where effective Coulomb interactions may change their sign. Our investigation is, thus, focused on Li, Na, K, Mg, Al, and Zn—they are representative elements from the alkali, alkaline earth, and post- transition metal groups. Given remarkable agreement demonstrated in Fig. 8, our strategy is to use Eq. (35) for the effective e- ph attraction from DFPT in combination with our Coulomb pseudopotential data to compute \(T_{c}\) for several simple metals. This analysis showcases the effectiveness of the EFT approach to \(\mu^{*}\) through higher accuracy of \(T_{c}\) predictions and new insights into the prospects of low- \(T_{c}\) superconductivity.   

### A. Methods  

To obtain band structures and phonon spectra we employed Quantum Espresso (QE) [94- 96] package. In all calculations the optimized norm- conserving Vanderbilt (ONCV) potential [97, 98] and Perdew- Burke- Ernzerhof (PBE) exchange- correlation functional [99] were used. Metallic crystals considered in this work form either FCC, or BCC, or HCP Bravais lattices. To investigate pressure effects, the lattice constants (specifically for Al) were determined via a fitted equation of state from Ref. [100]; a detailed discussion is provided in the Appendix F. For the self- consistent- field (SCF) calculation, the energy cutoff was set to 90 Ry, the momentum- grid had \(24 \times 24 \times 24\) , \(24 \times 24 \times 24\) , \(24 \times 24 \approx 12\) points for the FCC, BCC, and HCP structures, respectively. The error on the converged total energy was less than 0.001 Ry per atom. Phonons were calculated using the DFPT approach of Ref. [90], which was implemented within the QE package. A coarse \(\mathbf{q}\) - grid for the FCC, BCC, and HCP lattices contained \(6 \times 6 \times 6\) , \(6 \times 6 \times 6\) , and \(6 \times 6 \times 3\) points, respectively, and the acoustic sum rule was used to eliminate the small imaginary frequency at the \(\Gamma\) point.  

To get the e- ph coupling constant \(\lambda\) , we used the EPW package [15, 16], which evaluates e- ph interaction for Wannier functions, and subsequent Fourier interpolation to obtain the e- ph interaction defined on an arbitrary \(\mathbf{k}, \mathbf{q}\) grid. Wannier functions were generated by the Wannier90 package [101- 103] using coarse \(\mathbf{k}\) - grids for the FCC, BCC, and HCP lattices with \(12 \times 12 \times 12\) , \(12 \times 12 \times 12\) , and \(12 \times 12 \times 6\) points, respectively. The Wannier projectors for Li, Na, K, Mg, Al were set to \(s\) and \(p\) orbitals, and the ones for Zn are \(s\) , \(p\) , \(d\) orbitals. To get a converged result for \(\lambda\) , we set a fine \(\mathbf{k}\) (q) grid for the FCC, BCC, and HCP lattices with \(60 \times 60 \times 60\) ,




TABLE II. First-Principle Calculation Results of Selected Simple Metals   

<table><tr><td></td><td>Tf(103K)</td><td>ωlog a(K)</td><td>λpreb</td><td>λ</td><td>rsc</td><td>mb</td><td>μ*</td><td>TEFT(K)</td><td>Texp(K)</td><td>TμMAf(K)</td></tr><tr><td>Li(9R)</td><td>40</td><td>242d</td><td>0.34d</td><td>0.34d</td><td>3.25f</td><td>1.75e</td><td>0.18</td><td>5 × 10-3</td><td>4 × 10-4</td><td>0.35</td></tr><tr><td>Li(hcp)</td><td>41</td><td>243</td><td>0.33d</td><td>0.37</td><td>3.19</td><td>1.4</td><td>0.17</td><td>0.03</td><td>4 × 10-4</td><td>0.64</td></tr><tr><td>Na</td><td>42</td><td>127</td><td>0.181</td><td>0.2</td><td>3.96</td><td>1.0</td><td>0.15</td><td>2 × 10-13</td><td></td><td>6 × 10-5</td></tr><tr><td>K</td><td>26</td><td>85</td><td>0.132</td><td>0.11</td><td>4.86</td><td>1.0</td><td>0.16</td><td>No SC</td><td></td><td>10-120</td></tr><tr><td>Mg</td><td>80</td><td>269</td><td>0.237</td><td>0.24</td><td>2.66</td><td>1.02</td><td>0.14</td><td>5 × 10-5</td><td></td><td>0.007</td></tr><tr><td>Al</td><td>130</td><td>320</td><td>0.402</td><td>0.44</td><td>2.07</td><td>1.05</td><td>0.13</td><td>0.96</td><td>1.2</td><td>1.9</td></tr><tr><td>Zn</td><td>121</td><td>111</td><td>0.508</td><td>0.502</td><td>2.90</td><td>1.0</td><td>0.12</td><td>0.874</td><td>0.875</td><td>1.37</td></tr></table>

a The log-averaged frequency is calculated following Ref. [14]. b Previous results for e-ph coupling \(\lambda_{\mathrm{prev}}\) (mostly from Ref.[60] except for lithium) are shown for comparison with current \(\lambda\) estimates. c Wigner-Seitz radius \(r_{\mathrm{s}}\) computed from the lattice constant and conduction electron properties from DFT calculations. d Electron-phonon coupling in lithium for 9R and hcp structures [92]. We computed the hcp case, but also adapted results from literature for the 9R case. d Data for \(r_{\mathrm{s}}\) and \(m_{\mathrm{b}}\) in lithium were adapted from Ref.[93]. \(T_{\mu \mathrm{MA}}\) is the McMillan's formula [13] prediction using standard \(\mu^{*} = 0.1\) value.  

![](images/14_0.jpg)

<center>FIG. 10. The pressure dependence of the superconducting critical temperature in aluminum. The squares are our theoretical results; the lines are guides to the eye. Experimental data from Levy et al. [104] and Gubser et al. [105] are plotted as diamond and circular markers, respectively. </center>  

\(60\times 60\times 60\) , and \(60\times 60\times 30\) points, respectively.  

To decide what Coulomb pseudopotential to use, we fit the band structure of considered metals with the UEG model. The UEG density is set to be that of conduction electrons, and bare mass in the UEG model is extracted from the curvature of the band dispersion relation at the \(\Gamma\) point. This band mass, \(m_{\mathrm{b}}\) , effectively rescales the \(r_{\mathrm{s}}\) parameter \(r_{\mathrm{s}}\rightarrow (m_{\mathrm{b}} / m)r_{\mathrm{s}}\) . Effective mass renormalization in UEG is very small, and we assume that the same is true in our case, i.e. \(m_{\mathrm{b}}\) can be interpreted as the true quasiparticle effective mass. The Fermi energy \(E_{\mathrm{F}}\) is determined by the difference between the calculated Fermi energy and energy at the \(\Gamma\) point. Next, we interpolate pre- computed UEG results for Coulomb pseudopotential at rescaled value of \(r_{\mathrm{s}}\) , see Fig. 4, to obtain the effective pseudopotential at the Fermi energy, \(\mu_{E_{F}}\) of Eq. (25).  

### B. Results  

In Fig. 10, we compare the experimental data for the pressure- dependent \(T_{\mathrm{c}}\) in aluminum [104, 105] with the corresponding results of our approach (up to the highest reported pressure). We see that our approach accurately captures the experimental trend, showing a clear decrease in \(T_{\mathrm{c}}\) as pressure increases from ambient conditions to 6 GPa.  

Although similar benchmarks using the SCDFT method [58] also show good agreement with the experiment, the treatment of Coulomb repulsion within SCDFT involves uncontrolled approximations with respect to vertex corrections, screening dynamics, and quasiparticle weight. In contrast, our approach is based on a rigorous microscopic foundation and clear understanding of how one should proceed in cases significantly different from UEG. We performed calculations beyond the current experimental pressure limit of 6 GPa; see the inset of Fig. 10 and Fig. 11. Assuming no structural transitions, we predict that SC in Al vanishes at pressure 60GPa. Notably, even at 20 GPa, \(T_{\mathrm{c}}\) is already suppressed below 1 mK, rendering it undetectable with current experimental techniques.  

With the same numeric protocol, we calculated \(T_{\mathrm{c}}\) for other simple metals; the results are presented in Fig. 11 and TABLE II. Given \(T_{\mathrm{c}} / \omega_{\mathrm{log}}\propto \exp (- 1 / g)\) scaling, we choose to plot all data using \(y = 1 / \ln (\omega_{\mathrm{log}} / Tc)\) for the vertical axis, which may be considered as an effective attractive coupling in the Cooper channel (if \(T_{\mathrm{c}}\) is finite) for a given \(\mu^{*}\) and \(\lambda\) (here \(\omega_{\mathrm{log}}\) is the log- averaged phonon frequency calculated following Ref. [14]).  

The solid points in Fig. 11 and values given in Table I are our predictions. We see that for Na and Mg the predicted transition temperatures are so low that they cannot yet be probed with existing experimental techniques. For Li, our first- principles approach is significantly lower than existing estimates for \(T_{\mathrm{c}}\) , but still remains about an order of magnitude higher than the reported experimental value, in part due to the existing controversy with respect to the lattice structure at extremely low temper


![](images/15_0.jpg)

<center>FIG. 11. Effective BCS coupling strength, plotted as \(-1 / \ln (T_{c} / \omega_{\mathrm{log}})\) , for simple metals. The e-ph couplings were taken from the DFPT calculations, while the pseudopotentials were extracted from the VDiagMC results. In addition to the ambient pressure results for Li, Na, Mg, Al, and Zn, we also computed the pressure dependence of \(T_{c}\) in Al. Potassium is not shown, as our calculations predict it to be nonsuperconducting. We also show predictions based on McMillan's formula for different choices of \(\mu^{*}\) : 0 (cyan line), 0.1 (magenta line) 0.2 (orange line). We observe that our results for simple metals fall in between the conventional choices for \(\mu^{*}\) . Notably, \(\mu^{*}\) for two Li structures is larger than for other metals, resulting in \(T_{c}\) values much lower than estimated based on \(\mu \leq 0.15\) . Detailed values for \(T_{c}\) and \(\omega_{\mathrm{log}}\) are listed in Table I. </center>  

atures.  

We compare our results with those obtained from standard theories using a phenomenological \(\mu^{*}\) . The differences between the cyan, magenta- dot- dashed and orange- dashed lines in Fig. 11 show that uncertainties in the \(\mu^{*}\) values have a huge effect on the predicted \(T_{c}\) of these low- \(T_{c}\) materials, demonstrating that the phenomenological approach has no predictive power for low- temperature superconductors. We further see that some superconductors have ultra- low \(T_{c}\) not because \(\lambda\) is vanishingly small, but rather because the e- ph attraction is nearly balanced out by the e- e repulsion. On a practical note, precise values of \(\mu^{*}\) are particularly relevant for metals with \(T_{c}\) in the \(10\mathrm{mK}\) to \(1\mathrm{K}\) range, which is of interest to the superconducting electronics industry and thus highlight the need for a more thorough treatment of e- e scattering in real materials.  

Our results suggest that Mg, Na, and K are close to the critical point between states with and without s- wave SC. (We do not use the term "quantum critical point" here because SC in some other symmetry channel will preempt it.) Although these metals remain in the normal state as the temperature is lowered (e.g., well below \(1K\) ), they enter a quantum critical regime characterized by a diverging pair- field susceptibility \(\chi \sim \ln (T)\) [25] without any fine- tuning. This signal is worth verifying in future experiments.  

## VII. CONCLUSION  

We developed a rigorous ab initio framework, Fig. 9, to obtain downfolded ME theory on the Fermi surface for correlated electrons, which resolves long- standing ambiguities in the treatment of Coulomb repulsion. By systematically integrating out high- energy electronic degrees of freedom using field- theoretical renormalization techniques, we arrive at frequency- only ME equations with all parameters precisely linked to the underlying microscopic Hamiltonian: the Coulomb pseudopotential \(\mu^{*}\) , determined by the two- quasiparticle scattering amplitude renormalized by the Bogoliubov- Tolmachev- Shirkov logarithm [7, 8], the electron- phonon coupling \(\lambda\) screened by the quasiparticle vertex correction, and the quasiparticle density of states. Our approach eliminates the need for phenomenological—and thus uncontrolled—treatment of key parameters and establishes protocols for computing \(\mu^{*}\) and \(\lambda\) from the first principles.  

For \(\mu^{*}\) , high- order VDiagMC calculations for UEG reveal that pseudopotential values at the Fermi energy scale are significantly larger than estimates based on Yukawa or static- RPA screening. While UEG is barely a prototypical model featuring strong e- e correlations, its density- dependent \(\mu^{*}\) can be used to parameterize pseudopotentials in real materials. For \(\lambda\) , we confirm the accuracy of DFPT by comparing its predictions to our many- body vertex- corrected e- ph coupling, finding excellent agreement for UEG. By combining these results with observation that effective mass renormalization in the Coulomb system is negligibly small, we arrive at fitting- free predictions for \(T_{c}\) in simple metals with an order- of- magnitude improvement for sub- Kelvin superconductors. In particular, we predict that s- wave superconductivity in aluminum is suppressed to zero at 60 GPa, and that pair- susceptibility in Mg and Na should exhibit quantum critical scaling below \(10\mathrm{K}\) . These are testable predictions following from the interplay between the Coulomb repulsion and phonon- mediated attraction. The accuracy of the above- mentioned results rests on the power of precursory Cooper flow of the anomalous vertex correction to predict ultra- low \(T_{c}\) and critical points from normal state calculations.  

The ab initio framework of Fig. 9 applies not only to simple metals but to any other correlated material with well- defined quasiparticles at the Fermi surface and large separation between the phonon and electron energy scales \(\omega_{\mathrm{D}} \ll E_{\mathrm{F}}\) , \(\omega_{\mathrm{p}}\) . However, implementing high- order diagrammatics and renormalization, as it was done for UEG, is a major technical challenge for lattice systems with complex band structure lacking spherical symmetry. For example, in transition metals more than one band is involved in screening [106] and Umklapp processes cannot be neglected. In cases including two dimensional systems the particle- particle channel Coulomb interaction is non- local (not well approximated by a structureless interaction and as noted by Simonato, Katsnelson and Rosner [18] a more careful treatment is required. If the energy



scale separation condition, on which the downfolding approximation rests, is not satisfied, e.g. at extreme densities relevant to astrophysical objects such as white and black dwarf stars [62], or perhaps in flat- band systems and 2D materials where the \(\sqrt{q}\) plasmon dispersion creates challenges to the energy scale separation arguments there may be no real alternative to working with full BSE.  

Our findings highlight the crucial role of e- e correlations in the two- particle vertex function; they cannot be quantified by the single- electron exchange- correlation potential within the DFT approximation [72, 73]. Modern numerical methods like VDiagMC enable accurate computation of these correlations, providing key insights into the topic of paring despite strong repulsive forces, and opening new possibilities for understanding other emergent phenomena, such as accurate calculation of many- body forces in metals, with direct implications for more reliable molecular dynamics simulations. In conclusion, by providing a complete and predictive first- principles framework for incorporating e- e correlations into the existing machinery of predicting superconductivity from e- ph interaction, this work represents a step forward in our ability to predict superconductivity starting from properties of the microscopic Hamiltonian without uncontrolled approximations.   

## ACKNOWLEDGMENTS  

ACKNOWLEDGMENTSWe thank S. Das Sarma and A. Chubukov for valuable discussions. K. Chen and X. Cai are supported by the National Natural Science Foundation of China under Grants No. 12474245 and No. 12447103, the National Key Research and Development Program of China under Grant No.2024YFA1408604, and the GHfund A (202407010637). X. Cai and T. Wang acknowledge support from the National Science Foundation under Grant No. DMR- 2335904. T. Zhang and S. Zhang acknowledge the support from National Key R&D Project (Grant Nos. 2023YFA1407400 and 2024YFA1409200), and the National Natural Science Foundation of China (Grant Nos. 12374165 and 12447101). A. Millis's work at Columbia University was supported by the Keele Foundation and the Columbia University Materials Research Science and Engineering Center (MRSEC) through NSF Grant DMR- 2011738. N. Prokof'ev and B. Svistunov acknowledge support from the Simons Foundation (SFI- MPS- NFS- 00006741- 07, N.P. a B.S.) in the Simons Collaboration on New Frontiers in Superconductivity. The Flatiron Institute is a division of the simons foundation.  

[1] H. Frohlich, Theory of the Superconducting State. I. The Ground State at the Absolute Zero of Temperature, Physical Review 79, 845 (1950). [2] C. A. Reynolds, B. Serin, W. H. Wright, and L. B. Nesbitt, Superconductivity of Isotopes of Mercury, Physical Review 78, 487 (1950). [3] E. Maxwell, Isotope Effect in the Superconductivity of Mercury, Physical Review 78, 477 (1950). [4] L. N. Cooper, Bound Electron Pairs in a Degenerate Fermi Gas, Physical Review 104, 1189 (1956). [5] J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Theory of Superconductivity, Physical Review 108, 1175 (1957). [6] J. Bardeen, L. N. Cooper, and J. R. Schrieffer, Microscopic Theory of Superconductivity, Physical Review 106, 162 (1957). [7] N. N. Bogoliubov, V. V. Tolmachov, and D. Shirkov, A new method in the theory of superconductivity (Consultants Bureau, New York, 1959). [8] V. V. Tolmachev, Logarithmic criterion for superconductivity, in Doklady Akademii Nauk, Vol. 140 (Russian Academy of Sciences, 1961) pp. 563- 566. [9] P. Morel and P. W. Anderson, Calculation of the superconducting state parameters with retarded electron- phonon interaction, Phys. Rev. 125, 1263 (1962). [10] A. Migdal, Interaction between electrons and lattice vibrations in a normal metal, Sov. Phys.- JETP 7 (1958). [11] G. Eliashberg, Interactions between electrons and lattice vibrations in a superconductor, Sov. Phys. JETP 11, 696 (1960). [12] G. Eliashberg, Temperature green's function for electrons in a superconductor, Sov. Phys. JETP 12, 1000  

[13] W. L. McMillan, Transition temperature of strong- coupled superconductors, Phys. Rev. 167, 331 (1968). [14] P. B. Allen and R. C. Dynes, Transition temperature of strong- coupled superconductors reanalyzed, Phys. Rev. B 12, 905 (1975). [15] F. Giustino, M. L. Cohen, and S. G. Louie, Electron- phonon interaction using wannier functions, Phys. Rev. B 76, 165108 (2007). [16] S. Ponce, E. Margine, C. Verdi, and F. Giustino, Epw: Electron- phonon coupling, transport and superconducting properties using maximally localized wannier functions, Computer Physics Communications 209, 116 (2016). [17] E. R. Margine and F. Giustino, Anisotropic Migdal- Eliashberg theory using Wannier functions, Physical Review B 87, 024505 (2013). [18] M. Simonato, M. I. Katsnelson, and M. Rosner, Revised tolmachev- morel- anderson pseudopotential for layered conventional superconductors with nonlocal coulomb interaction, Phys. Rev. B 108, 064513 (2023). [19] D. Rainer, Chapter 4: Principles of ab initio calculations of superconducting transition temperatures (Elsevier, 1986) pp. 371- 424. [20] Y. Takada, Plasmon mechanism of superconductivity in two- and three- dimensional electron systems, Journal of the Physical Society of Japan 45, 786 (1978). [21] Y. Takada, s- and p- wave pairings in the dilute electron gas: Superconductivity mediated by the coulomb hole in the vicinity of the wigner- crystal phase, Phys. Rev. B 47, 5202 (1993).



[22] H. Rietschel and L. J. Sham, Role of electron coulomb interaction in superconductivity, Phys. Rev. B 28, 5100 (1983).[23] T. Wang, X. Cai, K. Chen, B. V. Svistunov, and N. V. Prokof'ev, Origin of the coulomb pseudopotential, Phys. Rev. B 107, L140507 (2023).[24] X. Cai, T. Wang, N. V. Prokof'ev, B. V. Svistunov, and K. Chen, Superconductivity in the uniform electron gas: Irrelevance of the kohn- luttinger mechanism, Phys. Rev. B 106, L220502 (2022).[25] P. Hou, X. Cai, T. Wang, Y. Deng, N. V. Prokof'ev, B. V. Svistunov, and K. Chen, Precursory cooper flow in ultralow- temperature superconductors, Phys. Rev. Res. 6, 013099 (2024).[26] S. D. Sarma, J. D. Sau, and Y.- T. Tu, Conventional and practical metallic superconductivity arising from repulsive Coulomb coupling (2025), arXiv:2511.00625 [cond-mat].[27] R. Akashi, Revisiting homogeneous electron gas in pursuit of properly normed ab initio eliashberg theory, Phys. Rev. B 105, 104510 (2022).[28] K. Irwin and G. Hilton, Transition- Edge Sensors, in Cryogenic Particle Detection, Topics in Applied Physics, edited by C. Enss (Springer, Berlin, Heidelberg, 2005) pp. 63- 150. [29] J. Aumentado, G. Catelani, and K. Serniak, Quasiparticle poisoning in superconducting quantum computers, Physics Today 76, 34 (2023).[30] C. Pellegrini and A. Sanna, Ab initio methods for superconductivity, Nature Reviews Physics 6, 509 (2024).[31] C. F. Richardson and N. W. Ashcroft, Effective electron- electron interactions and the theory of superconductivity, Phys. Rev. B 55, 15130 (1997).[32] J. Bauer, J. E. Han, and O. Gunnarsson, Retardation effects and the coulomb pseudopotential in the theory of superconductivity, Phys. Rev. B 87, 054507 (2013).[33] J. Tuoriniemi, K. Juntunen- Nurmilaikas, J. Uusvuori, E. Pentti, A. Salmela, and A. Sebedash, Superconductivity in lithium below 0.4 millikelvin at ambient pressure, Nature 447, 187 (2007).[34] J. P. Carbotte, Properties of boson- exchange superconductors, Rev. Mod. Phys. 62, 1027 (1990).[35] A. Subedi and L. Boeri, Vibrational spectrum and electron- phonon coupling of doped solid picene from first principles, Phys. Rev. B 84, 020508 (2011).[36] M. Kostrzewa, R. Szczesniak, J. K. Kalaga, and I. A. Wrona, Anomalously high value of Coulomb pseudopotential for the H5S2 superconductor, Scientific Reports 8, 11957 (2018).[37] E. Margine, H. Lambert, and F. Giustino, Electron- phonon interaction and pairing mechanism in superconducting ca- intercalated bilayer graphene, Scientific Reports 6, 21414 (2016).[38] W. Sano, T. Koretsune, T. Tadano, R. Akashi, and R. Arita, Effect of van hove singularities on high- \(T_{\mathrm{c}}\) superconductivity in \(\mathrm{h}_3\mathrm{S}\) , Phys. Rev. B 93, 094525 (2016).[39] D. J. Scalapino, The electron- phonon interaction and strong- coupling superconductors, Superconductivity: Part 1 (In Two Parts) 1, 449 (1969).[40] G. Gladstone, M. Jensen, and J. Schrieffer, Superconductivity in the transition metals: Theory and experiment, Superconductivity: Part 2 (In Two Parts) 2, 665 (1969).[41] F. Giustino, Electron- phonon interactions from first  

principles, Reviews of Modern Physics 89, 015003 (2017).[42] R. Akashi, Revisiting homogeneous electron gas in pursuit of properly normed ab initio eliashberg theory, Phys. Rev. B 105, 104510 (2022).[43] V. I. Anisimov, A. I. Poteryaev, M. A. Korotin, A. O. Anokhin, and G. Kotliar, First- principles calculations of the electronic structure and spectra of strongly correlated systems: Dynamical mean- field theory, Journal of Physics: Condensed Matter 9, 7359 (1997).[44] G. Kotliar, S. Y. Savrasov, K. Haule, V. S. Oudovenko, O. Parcollet, and C. A. Marianetti, Electronic structure calculations with dynamical mean- field theory, Reviews of Modern Physics 78, 865 (2006).[45] K. Haule, C.- H. Yee, and K. Kim, Dynamical mean- field theory within the full- potential methods: Electronic structure of \(\mathbb{S}\{\backslash \mathrm{text}\{\mathrm{CeIrIn}\} \} \_ \mathrm{5}\} \mathbb{S}\) , \(\mathbb{S}\{\backslash \mathrm{text}\{\mathrm{CeCoIn}\} \} \_ \mathrm{5}\} \mathbb{S}\) , and \(\mathbb{S}\{\backslash \mathrm{text}\{\mathrm{CeRhIn}\} \} \_ \mathrm{5}\} \mathbb{S}\) , Physical Review B 81, 195107 (2010).[46] D. N. Basov, R. D. Averitt, D. van der Marel, M. Dressel, and K. Haule, Electrodynamics of correlated electron materials, Reviews of Modern Physics 83, 471 (2011).[47] H. Park, A. J. Millis, and C. A. Marianetti, Computing total energies in complex materials using charge self- consistent DFT + DMFT, Physical Review B 90, 235103 (2014).[48] A. Paul and T. Birol, Applications of DFT + DMFT in Materials Science, Annual Review of Materials Research 49, 31 (2019).[49] C. P. Koger, K. Haule, G. L. Pascut, and B. Monserrat, Efficient lattice dynamics calculations for correlated materials with \(\mathbb{S}\backslash \mathrm{mathrm{DFT}}\backslash \mathrm{mathrm{DMFT}}\mathbb{S}\) , Physical Review B 102, 245104 (2020).[50] J. Karp, A. Hampel, and A. J. Millis, Superconductivity and antiferromagnetism in \(\mathbb{S}\{\backslash \mathrm{mathrm{NdNiO}}\} \_ \mathrm{2}\} \mathbb{S}\) and \(\mathbb{S}\{\mathrm{mathrm{CaCuO}}\} \_ \mathrm{2}\} \mathbb{S}\) : A cluster DMFT study, Physical Review B 105, 205131 (2022).[51] I. Esterlis, B. Nosarzewski, E. W. Huang, B. Moritz, T. P. Devereaux, D. J. Scalapino, and S. A. Kivelson, Breakdown of the migdal- eliashberg theory: A determinant quantum monte carlo study, Phys. Rev. B 97, 140501 (2018).[52] A. V. Chubukov, A. Abanov, I. Esterlis, and S. A. Kivelson, Eliashberg theory of phonon- mediated superconductivity—when it is valid and how it breaks down, Annals of Physics 417, 168190 (2020).[53] C. Zhang, J. Sous, D. R. Reichman, M. Berciu, A. J. Millis, N. V. Prokof'ev, and B. V. Svistunov, Bipolaronic high- temperature superconductivity, Phys. Rev. X 13, 011010 (2023).[54] C. F. Richardson and N. W. Ashcroft, High temperature superconductivity in metallic hydrogen: Electron- electron enhancements, Phys. Rev. Lett. 78, 118 (1997).[55] Y. in't Veld, M. I. Katsnelson, A. J. Millis, and M. Rosner, Screening induced crossover between phonon- and plasmon- mediated pairing in layered superconductors, 2D Materials 10, 045031 (2023).[56] M. Luders, M. A. L. Marques, N. N. Lathiotakis, A. Floris, G. Profeta, L. Fast, A. Continenza, S. Massidda, and E. K. U. Gross, Ab initio theory of superconductivity. I. Density functional formalism and approximate functionals, Physical Review B 72, 024545 (2005).



[57] M. A. L. Marques, M. Lüders, N. N. Lathiotakis, G. Profeta, A. Floris, L. Fast, A. Continenza, E. K. U. Gross, and S. Massidda, Ab initio theory of superconductivity. II. Application to elemental metals, Physical Review B 72, 024546 (2005).[58] G. Profeta, C. Franchini, N. N. Lathiotakis, A. Floris, A. Sanna, M. A. L. Marques, M. Lüders, S. Massidda, E. K. U. Gross, and A. Continenza, Superconductivity in Lithium, Potassium, and Aluminum under Extreme Pressure: A First-Principles Study, Physical Review Letters 96, 047003 (2006).[59] A. Sanna, J. A. Flores-Livas, A. Davydov, G. Profeta, K. Dewhurst, S. Sharma, and E. K. U. Gross, Ab initio eliashberg theory: Making genuine predictions of superconducting features, Journal of the Physical Society of Japan 87, 041012 (2018), https://doi.org/10.7566/JPSJ.87.041012. [60] M. Kawamura, Y. Hizume, and T. Ozaki, Benchmark of density functional theory for superconductors in elemental materials, Physical Review B 101, 134511 (2020).[61] B. Trubnikov, Are white dwarfs superconductors?, Zh. Eksp. Teor. Fiz 55, 1893 (1968).[62] V. L. Ginzburg and D. A. Kirzhniz, Superconductivity in White Dwarfs and Pulsars, Nature 220, 148 (1968).[63] N. V. Prokof'ev and B. V. Svistunov, Polaron Problem by Diagrammatic Quantum Monte Carlo, Physical Review Letters 81, 2514 (1998).[64] N. Prokof'ev and B. Svistunov, Fermi-polaron problem: Diagrammatic Monte Carlo method for divergent signal- alternating series, Physical Review B 77, 020408 (2008).[65] K. Van Houcke, E. Kozik, N. Prokof'ev, and B. Svistunov, Diagrammatic Monte Carlo, Physics Procedia Computer Simulations Studies in Condensed Matter Physics XXI, 6, 95 (2010).[66] R. Rossi, Determinant Diagrammatic Monte Carlo Algorithm in the Thermodynamic Limit, Physical Review Letters 119, 045701 (2017).[67] I. S. Tupitsyn and N. V. Prokof'ev, Diagrammatic Monte Carlo scheme for dielectric losses in metals, Physical Review B 111, L041106 (2025).[68] E. Kozik, Combinatorial summation of Feynman diagrams, Nature Communications 15, 7916 (2024).[69] K. Chen and K. Haule, A combined variational and diagrammatic quantum Monte Carlo approach to the many-electron problem, Nature Communications 10, 3725 (2019).[70] K. Haule and K. Chen, Single-particle excitations in the uniform electron gas by diagrammatic Monte Carlo, Scientific Reports 12, 2294 (2022).[71] J. Polchinski, Effective Field Theory and the Fermi Surface (1999), arXiv:hep-th/9210046. [72] P. Hohenberg and W. Kohn, Inhomogeneous Electron Gas, Physical Review 136, B864 (1964).[73] W. Kohn and L. J. Sham, Self-Consistent Equations Including Exchange and Correlation Effects, Physical Review 140, A1133 (1965).[74] A. Chubukov, N. V. Prokof'ev, and B. V. Svistunov, Implicit renormalization approach to the problem of cooper instability, Phys. Rev. B 100, 064513 (2019).[75] R. Shankar, Renormalization-group approach to interacting fermions, Rev. Mod. Phys. 66, 129 (1994).[76] K. Haule and K. Chen, Single-particle excitations in the uniform electron gas by diagrammatic Monte Carlo, Scientific Reports 12, 2294 (2022).  

[77] M. Holzmann, F. Calcavecchia, D. M. Ceperley, and V. Olevano, Static Self- Energy and Effective Mass of the Homogeneous Electron Gas from Quantum Monte Carlo Calculations, Physical Review Letters 131, 186501 (2023).[78] M. I. Katsnelson, A. J. Millis, M. Rösner, et al., Screening induced crossover between phonon- and plasmon- mediated pairing in layered superconductors, 2D Materials 10, 045031 (2023).[79] W. L. McMillan, Ground State of Liquid He\(^4\), Physical Review 138, A442 (1965).[80] D. Ceperley, G. V. Chester, and M. H. Kalos, Monte Carlo simulation of a many- fermion study, Physical Review B 16, 3081 (1977).[81] P. J. Reynolds, J. Tobochnik, and H. Gould, Diffusion Quantum Monte Carlo, Computer in Physics 4, 662 (1990).[82] P. Hou, T. Wang, D. Cerkoney, X. Cai, Z. Li, Y. Deng, L. Wang, and K. Chen, Feynman Diagrams as Computational Graphs (2024), arXiv:2403.18840 [cond- mat, physics:hep- ph, physics:hep- th, physics:physics].[83] J. Bettencourt, M. J. Johnson, and D. Duvenaud, Taylor- mode automatic differentiation for higher- order derivatives in JAX, in Program Transformations for ML Workshop at NeurIPS 2019 (2019).[84] A. Griewank and A. Walther, Evaluating derivatives: principles and techniques of algorithmic differentiation (SIAM, 2008).[85] S. Tan, Higher- Order Automatic Differentiation and Its Applications, Ph.D. thesis, Massachusetts Institute of Technology (2023).[86] G. Peter Lepage, A new algorithm for adaptive multidimensional integration, Journal of Computational Physics 27, 192 (1978).[87] G. P. Lepage, Adaptive Multidimensional Integration: VEGAS Enhanced, Journal of Computational Physics 439, 110386 (2021), arXiv:2009.05112 [hep- ph, physics:physics].[88] J. Brady, P. Wen, and J. W. Holt, Normalizing flows for microscopic many- body calculations: An application to the nuclear equation of state, Phys. Rev. Lett. 127, 062701 (2021).[89] A. J. Kim, N. V. Prokof'ev, B. V. Svistunov, and E. Kozik, Homotopic action: A pathway to convergent diagrammatic theories, Phys. Rev. Lett. 126, 257001 (2021).[90] S. Baroni, S. de Gironcoli, A. Dal Corso, and P. Giannozzi, Phonons and related crystal properties from density- functional perturbation theory, Rev. Mod. Phys. 73, 515 (2001).[91] M. Holzmann, F. Calcavecchia, D. M. Ceperley, and V. Olevano, Static self- energy and effective mass of the homogeneous electron gas from quantum monte carlo calculations, Phys. Rev. Lett. 131, 186501 (2023).[92] A. Y. Liu, A. A. Quong, J. K. Freericks, E. J. Nicol, and E. C. Jones, Structural phase stability and electron- phonon coupling in lithium, Physical Review B 59, 4028 (1999).[93] C. F. Richardson and N. W. Ashcroft, Effective electron- electron interactions and the theory of superconductivity, Physical Review B 55, 15130 (1997).[94] P. Giannozzi, S. Baroni, N. Bonini, M. Calandra, R. Car, C. Cavazzoni, D. Ceresoli, G. L. Chiarotti, M. Cococcioni, I. Dabo, A. D. Corso, S. de Giron



coli, S. Fabris, G. Fratesi, R. Gebauer, U. Gerstmann, C. Gougoussis, A. Kokalj, M. Lazzeri, L. Martin- Samos, N. Marzari, F. Mauri, R. Mazzarello, S. Paolini, A. Pasquarello, L. Paulatto, C. Sbraccia, S. Scandolo, G. Sclauzero, A. P. Seitsonen, A. Smogunov, P. Umari, and R. M. Wentzcovitch, Quantum espresso: a modular and open- source software project for quantum simulations of materials, Journal of Physics: Condensed Matter 21, 395502 (2009).[95] P. Giannozzi, O. Andreussi, T. Brumme, O. Bunau, M. B. Nardelli, M. Calandra, R. Car, C. Cavazzoni, D. Ceresoli, M. Cococcioni, N. Colonna, I. Carnimeo, A. D. Corso, S. de Gironcoli, P. Delugas, R. A. DiStasio, A. Ferretti, A. Floris, G. Fratesi, G. Fugallo, R. Gebauer, U. Gerstmann, F. Giustino, T. Gorni, J. Jia, M. Kawamura, H.- Y. Ko, A. Kokalj, E. Kucukbenli, M. Lazzeri, M. Marsili, N. Marzari, F. Mauri, N. L. Nguyen, H.- V. Nguyen, A. O. de- la Roza, L. Paulatto, S. Ponce, D. Rocca, R. Sabatini, B. Santra, M. Schlipf, A. P. Seitsonen, A. Smogunov, I. Timrov, T. Thonhauser, P. Umari, N. Vast, X. Wu, and S. Baroni, Advanced capabilities for materials modelling with quantum espresso, Journal of Physics: Condensed Matter 29, 465901 (2017).[96] P. Giannozzi, O. Baseggio, P. Bonfa, D. Brunato, R. Car, I. Carnimeo, C. Cavazzoni, S. de Gironcoli, P. Delugas, F. Ferrari Ruffino, A. Ferretti, N. Marzari, I. Timrov, A. Urru, and S. Baroni, Quantum ESPRESSO toward the exascale, The Journal of Chemical Physics 152, 154105 (2020).[97] D. R. Hamann, Optimized norm- conserving vanderbilt pseudopotentials, Phys. Rev. B 88, 085117 (2013).[98] M. Schlipf and F. Gygi, Optimization algorithm for the generation of oncv pseudopotentials, Computer Physics Communications 196, 36 (2015).[99] J. P. Perdew, K. Burke, and M. Ernzerhof, Generalized gradient approximation made simple, Phys. Rev. Lett. 77, 3865 (1996).[100] C. Friedli and N. W. Ashcroft, Aluminum under high pressure. i. equation of state, Phys. Rev. B 12, 5552 (1975).[101] G. Pizzi, V. Vitale, R. Arita, S. Blugel, F. Freimuth, G. Geranton, M. Gibertini, D. Gresch, C. Johnson, T. Koretsune, J. Ibanez- Azpiroz, H. Lee, J.- M. Lihm, D. Marchand, A. Marrazzo, Y. Mokrousov, J. I. Mustafa, Y. Nohara, Y. Nomura, L. Paulatto, S. Ponce, T. Ponweiser, J. Qiao, F. Thole, S. S. Tsirkin, M. Wierzbowska, N. Marzari, D. Vanderbilt, I. Souza, A. A. Mostofi, and J. R. Yates, Wannier90 as a community code: new features and applications, Journal of Physics: Condensed Matter 32, 165902 (2020).[102] N. Marzari and D. Vanderbilt, Maximally localized generalized wannier functions for composite energy bands, Phys. Rev. B 56, 12847 (1997).[103] I. Souza, N. Marzari, and D. Vanderbilt, Maximally localized wannier functions for entangled energy bands, Phys. Rev. B 65, 035109 (2001).[104] M. Levy and J. L. Olsen, Can pressure destroy superconductivity in aluminum?, Solid State Communications 2, 137 (1964).[105] D. U. Gubser and A. W. Webb, High- Pressure Effects on the Superconducting Transition Temperature of Aluminum, Physical Review Letters 35, 104 (1975).[106] G. Gladstone and M. A. Jensen and J. R. Schrieffer,  

Superconductivity in the transition metals: Theory and experiment, in Superconductivity, Vol. 2, edited by R. D. Parks (Marcel Dekker, Inc., New York, 1969) pp. 665- 816. [107] G. Stefanucci, R. van Leeuwen, and E. Perfetto, In and Out- of- Equilibrium Ab Initio Theory of Electrons and Phonons, Physical Review X 13, 031026 (2023).[108] R. M. Pick, M. H. Cohen, and R. M. Martin, Microscopic Theory of Force Constants in the Adiabatic Approximation, Physical Review B 1, 910 (1970).[109] A. A. Quong and B. M. Klein, Self- consistent- screening calculation of interatomic force constants and phonon dispersion curves from first principles, Physical Review B 46, 10734 (1992).  

## Appendix A: Field theoretical approach to the electron-phonon problem  

In this section, we employ the principles of effective field theory (EFT) to investigate the electron- phonon problem. Starting from a generic electron- ion model, we integrate out the ion vibration degrees of freedom to derive an EFT describing the coupled dynamics of electrons and phonons. Our derivation is distinguished by three key features that, to our knowledge, have not been collectively addressed in the existing literature on the electron- phonon problem.  

First, we do not approximate the electron- electron interactions using an exchange- correlation potential, as is commonly done in density functional theory (DFT) calculations[41]. This allows our derivation to remain applicable to strongly coupled materials. The only assumption we make is that the ions form a rigid lattice structure, implying that the vibration amplitude is small compared to the lattice spacing.  

Second, our derivation is applicable to generic electron- ion models with realistic lattice setups, making it suitable for ab- initio calculations of real materials. This generality ensures that our EFT can be used to study a wide range of systems, from simple metals to complex multicomponent materials.  

Third, we express the electron- phonon action in terms of the physical phonon dispersion using a renormalization scheme. This approach circumvents the need to introduce unphysical and potentially ill- defined bare phonon degrees of freedom, which can lead to complications in the interpretation of the results.  

The EFT framework we develop for the electron- phonon problem provides a solid foundation for systematically investigating the dynamics of electrons below the Fermi scale using field- theoretical techniques. This approach is particularly well- suited for studying the pairing mechanism of superconductivity, as it allows for a consistent treatment of the electron- electron and electron- phonon interactions, while also taking into account the realistic lattice structure of the material.



## Conventions  

To simplify notations, in appendices we adopted the following conventions. We used the integral and summation notions interchangeably. Unless otherwise claimed, the integral of a discrete variable were summation over the variable without any prefactors. Special cases were listed below. We interchangeably wrote integral and summation of momentums of electrons and phonons in the Brillouin zone, so that \(\begin{array}{r l r}{{\int_{\mathbf{q}} = \int_{\mathrm{BZ}}\frac{\mathrm{d}\mathbf{q}}{\Omega_{\mathrm{BZ}}} = \frac{1}{N}\sum_{\mathbf{q}},}} \end{array}\) where \(\Omega_{\mathrm{BZ}}\) is the volume of Brillouin zone. For Gvector \(\mathbf{G}_{m}\) and position in a unit cell \(\Delta \mathbf{r}\) , we have \(\begin{array}{r}{\int_{\Delta \mathbf{r}} = \int_{\Omega_{\mathrm{cell}}}\mathrm{d}(\Delta \mathbf{r})} \end{array}\) , where \(\Omega_{\mathrm{cell}}\) represents the volume of a unit cell, and \(\begin{array}{r}{\int_{\mathbf{G}_{m}} = \frac{1}{\Omega_{\mathrm{cell}}}\sum_{m}} \end{array}\) . For imaginary time \(\tau\) and Matsubara frequency \(\omega_{n}\) , we have \(\begin{array}{r}{\int_{\tau} = \int_{0}^{\beta}\mathrm{d}\tau} \end{array}\) and \(\begin{array}{r}{\int_{\omega_{n}} = T\sum_{n}} \end{array}\) , where \(\begin{array}{r}{T = \frac{1}{\beta}} \end{array}\) is the temperature.  

## 1 Electron-ion Model  

In this subsection, we present a concise review of the electron- ion problem from first principles, following a derivation adapted from Ref. [107]. We consider a solidstate system composed of electrons and ions, where the ions form a rigid lattice with equilibrium positions \(\mathbf{R}^{0} =\) \((\mathbf{R}_{1}^{0},\ldots ,\mathbf{R}_{N_{n}}^{0})\) . Due to quantum and thermal fluctuations, the ions oscillate around their equilibrium positions with small amplitudes \(\mathbf{u} = (\mathbf{u}_{1},\ldots ,\mathbf{u}_{N_{n}})\) . At a given time, the ions are located at coordinates \(\mathbf{R}\equiv \mathbf{R}^{0} + \mathbf{u}\) . The electrons and ions are governed by the full Hamiltonian:  

\[\hat{H} = \hat{H}_{\mathrm{e}} + \hat{H}_{\mathrm{n}} + \hat{H}_{\mathrm{en}}. \quad (A1)\]  

where \(\hat{H}_{\mathrm{e}}\) , \(\hat{H}_{\mathrm{n}}\) , and \(\hat{H}_{\mathrm{en}}\) represent the electron, ion, and electron- ion interaction terms, respectively.  

The ion Hamiltonian, \(\hat{H}_{\mathrm{n}}\) , consists of the kinetic energy of the ions and the potential energy due to the Coulomb interaction between the ions:  

\[\hat{H}_{\mathrm{n}} = \sum_{i = 1}^{N_{\mathrm{n}}}\frac{\hat{\mathbf{P}}_{i}^{2}}{2M} +E_{\mathrm{nn}}(\mathbf{u}), \quad (A2)\]  

where \(\hat{\mathbf{P}}_{i}\) are the ion momentum operators, \(M_{i}\) are the ion masses, and \(E_{nn}\) is the ion potential energy,  

\[E_{\mathrm{nn}}(\mathbf{u})\equiv \frac{1}{2}\sum_{i\neq j}^{N_{n}}Z_{i}Z_{j}v(\mathbf{R}_{i} - \mathbf{R}_{j}), \quad (A3)\]  

with \(Z_{i}\) being the atomic number of the \(i\) - th ion, and \(v(\mathbf{R}_{i} - \mathbf{R}_{j})\equiv e^{2} / |\mathbf{R}_{i} - \mathbf{R}_{j}|\) representing the Coulomb repulsion between ions.  

The electron part of the Hamiltonian, \(\hat{H}_{e}\) , is given by  

\[\hat{H}_{\mathrm{e}} = \int_{\mathbf{r}\sigma}\hat{\psi}_{\mathbf{r}\sigma}^{\dagger}\left[-\frac{\nabla^{2}}{2m} +V_{\mathbf{r}}^{0}\right]\hat{\psi}_{\mathbf{r}\sigma}\] \[\qquad +\frac{1}{2}\int_{\mathbf{r}\sigma^{\prime}}\hat{\psi}_{\mathbf{r}\sigma^{\prime}}^{\dagger}\hat{\psi}_{\mathbf{r}^{\prime}\sigma^{\prime}}^{\dagger}v(\mathbf{r} - \mathbf{r}^{\prime})\hat{\psi}_{\mathbf{r}^{\prime}\sigma^{\prime}}\hat{\psi}_{\mathbf{r}\sigma},\]  

where \(\hat{\psi}_{\mathbf{r}\sigma}\) is the field operator for electrons at the position \(\mathbf{r}\) with the spin index \(\sigma\) , \(m\) is the electron mass, and \(v(\mathbf{r} - \mathbf{r}^{\prime})\) is the electron- electron Coulomb repulsion. The electrons moving in an inhomogeneous background potential \(V_{\mathbf{r}}^{0}\) , which is a static potential generated by the ions  

\[V_{\mathbf{r}}^{\mathbf{u}}\equiv -\sum_{j = 1}^{N_{n}}Z_{j}\cdot v(\mathbf{R}_{j} - \mathbf{r}), \quad (A4)\]  

at their equilibrium position \(\mathbf{u} = 0\)  

The vibration of the ions around the equilibrium position induces an electron- ion interaction term, \(\hat{H}_{e - n}\) ,  

\[\hat{H}_{\mathrm{en}} = \int_{\mathbf{r}}\hat{n}_{\mathbf{r}}\left(V_{\mathbf{r}}^{\mathbf{u}} - V_{\mathbf{r}}^{0}\right). \quad (A5)\]  

where \(\begin{array}{r}{\hat{n}_{\mathbf{r}} = \sum_{\sigma}\hat{\psi}_{\mathbf{r}\sigma}^{\dagger}\hat{\psi}_{\mathbf{r}\sigma}} \end{array}\) is the electron density operator..  

To study the finite temperature superconductivity, we consider a solid at a given temperature \(T\) . The central quantity of interest is the partition function,  

\[Z = \mathrm{Tr}e^{-\beta \hat{H}}, \quad (A6)\]  

where \(\beta = 1 / k_{B}T\) , \(k_{B}\) is the Boltzmann constant, and \(\hat{H}\) is the Hamiltonian of the system. We work in the canonical ensemble with fixed ion and electron numbers.  

To derive the action formulation of the electron- ion model, we represent the partition function with a path integral over the ionic and electronic degrees of freedom,  

\[Z = \int_{\mathbf{u}}e^{-S_{\mathrm{n}}[\mathbf{u}]}\int_{\hat{\psi},\psi}e^{-S_{\mathrm{e}}[\hat{\psi},\psi]}e^{-S_{\mathrm{en}}[\mathbf{u},\hat{\psi},\psi ]}, \quad (A7)\]  

where \(S_{\mathrm{n}}\) , \(S_{\mathrm{e}}\) , and \(S_{\mathrm{en}}\) are the ion, electron, and electron- ion actions, respectively. The path integrals are performed over the ionic positions \(\mathbf{u}_{\tau}\) and the Grassmann fields \(\psi_{\mathbf{r}\tau}^{\sigma}\) and \(\hat{\psi}_{\mathbf{r}\tau}^{\sigma}\) , which represent the electrons. The imaginary time \(\tau\) runs from 0 to \(\beta\) , and the fields satisfy periodic (anti- periodic) boundary conditions for bosons (fermions).  

The electron Lagrangian, \(S_{\mathrm{e}}\) , describes the dynamics of the electrons and is given by  

The electron Lagrangian, \(S_{\mathrm{e}}\) , describes the dynamics of the electrons and is given by  

\[\begin{array}{l}{S_{\mathrm{e}} = \int_{\mathbf{r}\sigma \tau}\bar{\psi}_{\mathbf{r}\tau}^{\sigma}\left[\frac{\partial}{\partial\tau} -\frac{\nabla^{2}}{2m} +V_{\mathbf{r}}^{0}\right]\psi_{\mathbf{r}\tau}^{\sigma}}\\ {+\frac{1}{2}\int_{\mathbf{r}\sigma ,\mathbf{r}^{\prime}\sigma^{\prime},\tau}\bar{\psi}_{\mathbf{r}\tau}^{\sigma}\bar{\psi}_{\mathbf{r}^{\prime}\tau}^{\sigma^{\prime}}v(\mathbf{r} - \mathbf{r}^{\prime})\psi_{\mathbf{r}^{\prime}\tau}^{\sigma^{\prime}}\psi_{\mathbf{r}\tau}^{\sigma}.} \end{array} \quad (A8)\]  

The ion action, \(S_{\mathrm{n}}\) , describes the dynamics of the ions and is given by  

\[S_{\mathrm{n}} = \int_{\mathbf{r}}\left[\sum_{i = 1}^{N_{\mathrm{n}}}\frac{M_{i}}{2}\left(\frac{\partial\mathbf{u}_{i\tau}}{\partial\tau}\right)^{2} + E_{\mathrm{nn}}\left(\mathbf{u}_{\tau}\right)\right], \quad (A9)\]  

where the imaginary- time integration \(\begin{array}{r}{\int_{\tau}\equiv \int_{0}^{\beta}d\tau} \end{array}\) with \(\beta\) the inverse temperature.



The electron-ion Lagrangian, \(S_{\mathrm{en}}\) , describes the interaction between the electrons and ions and is given by  

\[S_{\mathrm{en}} = \int_{\mathbf{r}\sigma \tau}\bar{\psi}_{\mathbf{r}\tau}^{\sigma}\psi_{\mathbf{r}\tau}^{\sigma}\left(V_{\mathbf{r}}^{\mathbf{u}_{\tau}} - V_{\mathbf{r}}^{0}\right), \quad (A10)\]  

where \(V_{\mathbf{r}}^{\mathbf{u}_{\tau}}\) is the ionic potential with the ions at positions \(\mathbf{u}_{\tau}\) , and \(V_{\mathbf{r}}^{0}\) is the background ionic potential with the ions at their equilibrium positions.  

By expressing the partition function as a path integral over the ionic and electronic degrees of freedom, we can systematically investigate the electron- phonon problem with the standard field- theoretical techniques, as explained in the next subsection.  

## 2 Electron-Phonon Action  

In this subsection, we reinterpret the ion vibration degrees of freedom as propagating phonon modes and derive an effective field theory (EFT) for the electron- phonon problem based on the electron- ion action. Our approach takes advantage of the small vibration amplitude of the ions compared to the lattice constant, which allows us to systematically expand the electron- ion action in powers of the dimensionless parameter \(u / a \sim (m / M)^{1 / 4}\) , where \(m\) is the electron mass, \(M\) is the mass of the lightest ion species and \(a\) is the characteristic lattice spacing.  

We begin by expanding the ion potential energy, \(E_{\mathrm{nn}}(\mathbf{u}_{\tau})\) , up to second order in the ion displacement \(\mathbf{u}\) :  

\[E_{\mathrm{nn}}(\mathbf{u}_{\tau}) = E_{\mathrm{nn}}(0) + \frac{1}{2}\sum_{ij}\mathbf{u}_{i\tau}\cdot \frac{\partial^{2}E_{\mathrm{nn}}(\mathbf{u}\to 0)}{\partial\mathbf{u}_{i}\partial\mathbf{u}_{j}}\cdot \mathbf{u}_{j\tau} + O(u^{4}), \quad (A11)\]  

where the odd terms vanish due to symmetry. Similarly, we expand the ion potential in the electron- ion coupling, \(V_{\mathbf{r}}^{\mathbf{u}_{\tau}}\) , up to second order in \(\mathbf{u}\) :  

\[V_{\mathbf{r}}^{\mathbf{u}_{\tau}} = V_{\mathbf{r}}^{0} + \sum_{i}\mathbf{g}_{i}^{0}(\mathbf{r})\cdot \mathbf{u}_{i\tau} + \frac{1}{2}\sum_{ij}\mathbf{u}_{i\tau}\cdot \frac{\partial^{2}V_{\mathbf{r}}^{\mathbf{u}\to 0}}{\partial\mathbf{u}_{i}\partial\mathbf{u}_{j}}\cdot \mathbf{u}_{j\tau} + O(u^{3}) \quad (A12)\]  

where \(\mathbf{g}_{i}^{0} \equiv (g_{ix}^{0}, g_{iy}^{0}, g_{iz}^{0})\) is the bare electron- phonon coupling, defined as:  

\[g_{i\alpha}^{0}(\mathbf{r}) \equiv \frac{\partial V_{\mathbf{r}}^{\mathbf{u}\to 0}}{\partial u_{i\alpha}} = Z_{i}\frac{\partial}{\partial r_{\alpha}} v(\mathbf{r} - \mathbf{R}_{i}^{0}). \quad (A13)\]  

Note that we retain the linear term in the expansion of \(V_{\mathbf{r}}^{\mathbf{u}_{\tau}}\) because the electron density in Eq.(A10) is odd in \(\mathbf{u}\) . There is no need to go beyond \(O(u^{2})\) because, when the ion vibration degrees of freedom are integrated out, the electron- ion coupling always contributes in pairs.  

Applying the above approximations to the electron- ion action, then collecting terms of the same order in \(\mathbf{u}\) , we derive the electron- phonon action:  

\[S = S_{\mathrm{e}} + S_{\mathrm{ph}}^{0} + S_{\mathrm{e - ph}} + O\left(\frac{m}{M}\right) \quad (A14)\]  

where the \(O(u)\) term is the electron- phonon coupling:  

\[S_{\mathrm{e - ph}} = \sum_{i\alpha}\int_{\mathbf{r}\sigma \tau}g_{i\alpha}^{0}(\mathbf{r})\bar{\psi}_{\mathbf{r}\tau}^{\sigma}\psi_{\mathbf{r}\tau}^{\sigma}u_{i\alpha \tau} \quad (A15)\]  

and the \(O(u^{2})\) is identified as the bare phonon action,  

\[S_{\mathrm{ph}}^{0} = \int_{\tau}\left[\sum_{i\alpha}\frac{M_{i}}{2}\left(\frac{\partial u_{i\alpha\tau}}{\partial\tau}\right)^{2} - \frac{1}{2}\sum_{ij\alpha \beta}u_{i\alpha \tau}K_{i\alpha ;j\beta}u_{j\beta \tau}\right], \quad (A16)\]  

Here, \(K_{i\alpha ;j\beta}\) is the bare elastic tensor, given by:  

\[K_{i\alpha ;j\beta} \equiv \frac{\partial^{2}\left[E_{\mathrm{nn}}(\mathbf{u}\to 0) + \int_{\mathbf{r}}n_{\mathbf{r}}^{0}V_{\mathbf{r}}^{\mathbf{u}\to 0}\right]}{\partial u_{i\alpha}\partial u_{j\beta}}, \quad (A17)\]  

where the Greek letters \(\alpha\) and \(\beta\) labels the dimension of vector \(\mathbf{u}\) .  

It is important to note that bare elastic tensor \(K\) , which appears in the original formulation of the phonon action, is not directly measurable and may not even be a well- defined quantity in real materials. This is because the bare elastic tensor does not take into account the renormalization effects arising from the electron- phonon interaction and the electron correlations in the system. To avoid working with the unphysical bare parameters, it makes sense to re- express \(K\) with an effective elastic tensor \(K^{\mathrm{eff}}\) , which is a physically measurable quantity directly related to the phonon dispersion \(\omega_{\kappa \mathbf{q}}\) and can be probed by inelastic neutron scattering experiments. It is a linear response function with respect to the deformation of the ion positions:  

\[\begin{array}{l}{K_{i\alpha ;j\beta}^{\mathrm{eff}}\equiv \langle u_{i\alpha}u_{j\beta}\rangle}\\ {= K_{i\alpha ;j\beta} + \int_{\mathbf{r}_{1}\mathbf{r}_{2}}g_{i\alpha}^{0}(\mathbf{r}_{1})\chi_{i_{1}\mathbf{r}_{2}}^{e}g_{j\beta}^{0}(\mathbf{r}_{2}),} \end{array} \quad (A19)\]  

where the first term is the contribution from the direct ion- ion Coulomb interaction, and the second term is the contribution mediated by the many electron system, with \(\chi^{e}\) the static electron density- density correlation function,  

\[\chi_{r_{1}r_{2}}^{e} = \langle \hat{n}_{r_{1}}\hat{n}_{r_{2}}\rangle_{e} - \langle \hat{n}_{r_{1}}\rangle_{e}\langle \hat{n}_{r_{2}}\rangle_{e}, \quad (A20)\]  

The averages are taken with respect to the many- electron action in Eq.(A8), assuming all ions are fixed at the equilibrium positions.  

Re- expressing the bare quantity with the renormalized quantity using \(K = K_{\mathrm{eff}} + g^{0}\cdot \chi^{e}\cdot g^{0}\) , we replace the bare phonon action with an effective phonon action \(S_{\mathrm{ph}}\) and a counterterm \(S_{\mathrm{CT}}\) .  

The effective phonon action \(S_{\mathrm{ph}}\) , with their dispersion directly related to measurable quantities such as the neutron scattering amplitude, is given by:  

\[S_{\mathrm{ph}} = \int_{\tau}\left[\sum_{i\alpha}\frac{M_{i}}{2}\left(\frac{\partial u_{i\alpha\tau}}{\partial\tau}\right)^{2} - \frac{1}{2}\sum_{ij\alpha \beta}u_{i\alpha \tau}K_{i\alpha ;j\beta}^{\mathrm{eff}}u_{j\beta \tau}\right] \quad (A21)\]



The phonon action can be further simplified by diagonalizing the effective elastic tensor \(K^{\mathrm{eff}}\) using proper eigenvectors \(e_{s,\alpha}^{\kappa}(\mathbf{q})\) , where \(i = (\mathbf{n},s)\) with \(\mathbf{n}\) being a lattice vector, \(s\) labels different ions in a unit cell, and \(\kappa\) labels the branches of vibration modes, and \(\mathbf{q}\) is the reciprocal lattice momentum. The \(i\) - th atom position is then \(\mathbf{R}_{i} = \mathbf{n} + \delta \mathbf{r}_{s}\) , with \(\delta \mathbf{r}_{s}\) sublattice position of the atom. By inserting the following transformation:  

\[u_{\mathbf{n}s,\alpha} = \frac{1}{M_s}\int_{\mathbf{q}}e^{i\mathbf{q}\cdot \mathbf{n}}\sum_{\kappa}e_{s,\alpha}^{\kappa}(\mathbf{q})u_{\kappa \mathbf{q}}, \quad (A22)\]  

into the phonon action, we obtain:  

\[\begin{array}{l}{S_{\mathrm{ph}}[\mathbf{u}] = \frac{1}{2}\sum_{\kappa}\int_{\mathbf{q}\tau}\left[\left(\frac{\partial u_{\kappa\mathbf{q}\tau}}{\partial\tau}\right)^2 -\omega_{\kappa\mathbf{q}}^2 u_{\kappa \mathbf{q}\tau}^2\right]}\\ {= \frac{1}{2}\sum_{\kappa}\int_{\mathbf{q}\nu}D_{\kappa}^{-1}(\mathbf{q},\nu)\left|u_{\kappa \mathbf{q}\nu}\right|^2} \end{array} \quad (A23)\]  

where eigenvalues of effective elastic tensor \(\omega_{\kappa \mathbf{q}}\) the physical dispersion of the phonon mode. Function \(D_{\kappa}(\mathbf{q},\nu)\) is the Fourier transform of the phonon propagator \(D_{\kappa}(\mathbf{q},\tau - \tau^{\prime})\equiv - \langle T U_{\kappa \mathbf{q}\tau}U_{\kappa \mathbf{q}\tau^{\prime}}\rangle\) into the Matsubara- frequency representation:  

\[D_{\kappa}(\mathbf{q},\nu) = -\frac{1}{\nu^{2} + \omega_{\kappa\mathbf{q}}^{2}} \quad (A25)\]  

In the effective phonon action, the renormalized phonon dispersion has resumed the electron correlations. To avoid double- counting, a counterterm is required to compensate the resummation:  

\[S_{\mathrm{CT}} = -\frac{1}{2}\sum_{\kappa}\int_{\mathbf{q}\tau}g_{\kappa \mathbf{q}}^{0}(\mathbf{r}_{1})\chi_{\mathbf{r}_{1}\mathbf{r}_{2}}^{e}g_{\kappa \mathbf{q}}^{0}(\mathbf{r}_{2})u_{\kappa \mathbf{q}\tau}^{2}, \quad (A26)\]  

where the electron- phonon coupling in the reciprocal lattice momentum representation is given by:  

\[g_{\kappa \mathbf{q}}^{0}(\mathbf{r}) = \sum_{\mathbf{n}s\alpha}e^{i\mathbf{q}\cdot \mathbf{n}}e_{s,\alpha}^{\kappa}(\mathbf{q})g_{\mathbf{n}s\alpha}^{0}(\mathbf{r}). \quad (A27)\]  

Substituting the bare phonon action \(S_{\mathrm{eph}}^{0}\) in Eq.(A14) with the renormalized action \(S_{ph} + S_{CT}\) , we derive the effective field theory for the electron- phonon problem by integrating out the ion vibration degrees of freedom:  

\[S = S_{\mathrm{e}} + S_{\mathrm{ph}} + S_{\mathrm{ep - ph}} + S_{\mathrm{CT}} + O\left(\frac{m}{M}\right) \quad (A28)\]  

In summary, by expanding the electron- ion action in powers of the ion displacement and expressing the bare quantities in terms of physical observables, we have derived an effective field theory for the electron- phonon problem. This EFT captures the essential physics of the coupled electron- phonon system, with the phonon dispersion directly related to measurable quantities. The inclusion of counterterms ensures that the double- counting of electron correlation effects is systematically removed, providing a well- defined framework for studying the properties of electron- phonon systems in real materials.  

## 3 Electron-phonon interaction  

Now we return to the electron part of the action with the effective phonon action defined. The interaction term, then, becomes  

\[S_{\mathrm{e - ph}} = \sum_{\kappa \sigma}\int_{\mathbf{r}\mathbf{q}\tau}\bar{\psi}_{\mathbf{r}\tau}^{\sigma}\psi_{\mathbf{r}\tau}^{\sigma}g_{\kappa \mathbf{q}}^{0}(\mathbf{r})u_{\kappa \mathbf{q}\tau}. \quad (A29)\]  

The Eq.(A13) shows that the electron- phonon interaction \(g_{\kappa \mathbf{q}}(\mathbf{r})\) has the following property:  

\[g_{\kappa \mathbf{q}}^{0}(\mathbf{r} + \mathbf{n}) = e^{i\mathbf{q}\cdot \mathbf{n}}g_{\kappa \mathbf{q}}^{0}(\mathbf{r}), \quad (A30)\]  

when \(\mathbf{n}\) is a lattice vector. This property comes from the discrete translational invariance of the lattice.  

Then, we switch the electron part to the momentum space by defining  

\[\psi_{\mathbf{r}}^{\sigma} = \int_{\mathbf{k}\mathbf{G}_{m}}e^{i\mathbf{k}\mathbf{n}}e^{i\mathbf{G}_{m}\Delta \mathbf{r}}\psi_{\mathbf{k}}^{\sigma m\sigma}, \quad (A31)\]  

with \(\mathbf{r} = \mathbf{n} + \Delta \mathbf{r}\) , where \(\mathbf{n}\) is a lattice vector and \(\Delta \mathbf{r}\) is within a unit cell of volume \(\Omega_{\mathrm{Cell}}\) . The momentum \(\mathbf{k}\) is defined within the first Brillouin zone, and \(\mathbf{G}_{m}\) is the \(\mathrm{G}\) - vector. Plugging this into the interaction Lagrangian leads to  

\[S_{\mathrm{e - ph}} = \sum_{\sigma \kappa}\int_{\mathbf{k}\mathbf{q}\tau}g_{m m^{\prime}\kappa}^{0}(\mathbf{q})\bar{\psi}_{\mathbf{k} + \mathbf{q}\tau}^{m\sigma}\psi_{\mathbf{k}\tau}^{m^{\prime}\sigma}u_{\kappa \mathbf{q}\tau}, \quad (A32)\]  

with  

\[g_{m m^{\prime}\kappa}^{0}(\mathbf{q}) = \int_{\Delta \mathbf{r}}e^{-i(\mathbf{G}_{m} - \mathbf{G}_{m^{\prime}})\Delta \mathbf{r}}g_{\mathbf{q}\kappa}(\Delta \mathbf{r}). \quad (A33)\]  

The electron part of the action is now  

\[\begin{array}{r l r} & {} & {S_{\mathrm{e}} = \int_{\mathbf{k}\mathbf{r}\sigma}\sum_{\sigma}\bar{\psi}_{\mathbf{k}\tau}^{m\sigma}\left[\left(\frac{\partial}{\partial\tau} -\frac{(\mathbf{k} + \mathbf{G}_{m})^{2}}{2m}\right)\delta_{m m^{\prime}} + V_{m m^{\prime}}\right]\psi_{\mathbf{k}\tau}^{m^{\prime}\sigma}}\\ & {} & {G_{m}G_{m}^{\prime}}\\ & {} & {}\\ & {} & {+\frac{1}{2}\int_{\mathbf{k}\mathbf{k}^{\prime}\mathbf{q}\tau}\sum_{\sigma \sigma^{\prime}\tau}\bar{\psi}_{\mathbf{k}\tau}^{m\sigma}\bar{\psi}_{\mathbf{k}^{\prime}\tau}^{\sigma^{\prime}\sigma^{\prime}}v_{\mathbf{q} + \mathbf{G}_{n}}\psi_{\mathbf{k}^{\prime} - \mathbf{q}\tau}^{m^{\prime} - n\sigma^{\prime}}\psi_{\mathbf{k} + \mathbf{q}\tau}^{m + n\sigma},}\\ & {} & {\qquad \mathbf{G}_{m}G_{m}^{\prime}}\\ & {} & {\qquad \mathrm{(A34)}} \end{array} \quad (A34)\]  

with  

\[V_{m m^{\prime}} = \int_{\Delta \mathbf{r}}e^{-i(\mathbf{G}_{m} - \mathbf{G}_{m^{\prime}})\Delta \mathbf{r}}V(\Delta \mathbf{r},\mathbf{R}^{0}). \quad (A36)\]  

We abbreviate the notation of \(\mathrm{G}\) - vectors in subscripts of the field so that any arithmetic notation of indices should be understood as operation of corresponding \(\mathrm{G}\) - vectors, i.e., \(\psi^{m - n} = \psi (\mathbf{G}_{m} - \mathbf{G}_{n})\) . While the \(\mathrm{G}\) - vector remains conserved during scattering processes due to Coulomb interactions and the bare electron- phonon interaction, the lattice potential \(V_{m m^{\prime}}\) may introduce an external source of \(\mathrm{G}\) - vectors. Consequently, the Green's function for the electron could exhibit different incoming and outgoing \(\mathrm{G}\) - vectors.


![](images/23_0.jpg)

<center>FIG. 12. Electron's density-density correlation function \(\chi^{\mathrm{e}}\) from electron's polarization \(\Pi^{\mathrm{e}}\) . </center>  

![](images/23_1.jpg)

<center>FIG. 13. Electron-phonon interaction \(g\) from bare electron-phonon coupling \(g^{0}\) . </center>  

## 4 Screening of the Electron-phonon Interaction  

While the interaction between bare electrons and phonons is described by the electron-phonon coupling \(g^{0}\) , the quasiparticle counterpart \(g\) was screened by the electrons and dressed by the electron's 3- vertex. It turns out that this effect, together with the effect of quasiparticle renormalization factor \(z^{\mathrm{e}}\) , resulted in a net effect that could be neglected for practical purposes. In this section we derived the quantity that described this effect, and in later sections we would show the numerical results.  

The bare electron- phonon interaction \(g_{mm^{\prime}\kappa}^{0}(\mathbf{q})\) generally depends on the structure of the lattice and has complex structures in momentum space. Specifically, the bare electron- phonon interaction defined in Eq.(A13) diverges at \(\mathbf{q} = 0\) . However, after the screening effect was taken into account, the quasiparticle counterpart \(g\) would be regular. The screening effect was shown in the definition of \(g\) as illustrated in Fig.13.  

To simplify the discussion below, we split the lattice dependent part and the Coulomb singular part by writing \(g_{mm^{\prime}\kappa}^{0}(\mathbf{q}) = g_{mm^{\prime}\kappa}^{r}(\mathbf{q})v_{\mathbf{q}}\) , such that \(g^{\mathrm{r}}\) is a regular function at \(\mathbf{q} = 0\) . By plugging this definition into the definition of \(g\) , we obtain \(g(\mathbf{k}\omega ;\mathbf{q}\nu) = g^{r}z^{\mathrm{e}}W_{\mathbf{q}\nu}^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}}(\mathbf{k}\omega ;\mathbf{q}\nu)\) , where \(\frac{v_{\mathbf{q}}}{\epsilon_{\mathbf{q}\nu}} = W_{\mathbf{q}\nu}^{\mathrm{e}} = \frac{v_{\mathbf{q}}}{1 - v_{\mathbf{q}}P_{\mathbf{q}\nu}}\) is the screened Coulomb interaction between electrons, and \(P_{\mathbf{q}\nu}\) is the electron's polarization. Thus we could see that the screening effect is encoded in the structure of \(W_{\mathrm{3}}^{\mathrm{e}}\) . In Fig.8 we show the numerical results of \(z^{\mathrm{e}}W_{\mathrm{3}}^{\mathrm{e}}\) in UEG via VDMC, and in next section we discuss the connection between \(g\) and the ones obtained from first- principle methods such as DFPT.  

## 5 Density Functional Perturbation Theory of the Electron-Phonon Interaction  

We started by reviewing the derivation of the electron- phonon interaction within the framework of DFT. We followed the spirit of dielectric approach [108, 109], which  

is theoretically equivalent to the DFPT as pointed out in Ref.[15]. Starting from the effective potential experienced by an electron, we had the Kohn- Sham potential,  

\[V^{\mathrm{KS}}(\mathbf{r};\{\mathbf{R}_{0}\}) = V^{\mathrm{ion}}(\mathbf{r};\{\mathbf{R}_{0}\}) + V^{\mathrm{H}}(\mathbf{r};\{\mathbf{R}_{0}\}) + V^{\mathrm{xc}}[\mathbf{r};n(\{\mathbf{R}_{0}\})],\]  

where \(V^{\mathrm{ion}}\) is the potential from the ion lattice, \(V^{\mathrm{H}}\) is the Hartree energy, which is the electrostatic energy generated from \(n(\mathbf{r};\{\mathbf{R}_{0}\})\) . We assumed that the exchange- correlation effects between electrons could be captured by a functional \(V^{\mathrm{xc}}[\mathbf{r};n(\{\mathbf{R}_{0}\})]\) depending on the electron density. The dependence on \(n\) could be non- local in general; while for our purpose, it is sufficient to consider within LDA, where the potential at \(\mathbf{r}\) is given by a functional \(V^{\mathrm{xc}}[n(\mathbf{r};\{\mathbf{R}_{0}\})]\) depending only on the local electron density \(n(\mathbf{r};\{\mathbf{R}_{0}\})\) at \(\mathbf{r}\) . The density of electrons is in turn determined by an ionic potential imposed by the ions at the position \(\mathbf{R}^{0}\) .  

Now consider a small displacement of ions \(\delta \mathbf{R}\) , the response of the potential would be  

\[\delta V^{\mathrm{KS}}\equiv V^{\mathrm{KS}}(\mathbf{r};\{\mathbf{R}_{0} + \delta \mathbf{R}\}) - V^{\mathrm{KS}}(\mathbf{r};\{\mathbf{R}_{0}\}), \quad (A38)\]  

which was a sum of three components,  

\[\delta V^{\mathrm{ion}} = \sum_{i\alpha}g_{i\alpha}^{0}\delta R_{i\alpha}, \quad (A39)\]  

\[\delta V^{\mathrm{H}} = \int_{\mathbf{r}^{\prime}}v\left(\mathbf{r},\mathbf{r}^{\prime}\right)\delta n\left(\mathbf{r}^{\prime};\{\mathbf{R}_{0}\}\right), \quad (A40)\]  

and  

\[\delta V^{\mathrm{xc}} = \int_{\mathbf{r}^{\prime}}f_{\mathrm{xc}}(\mathbf{r},\mathbf{r}^{\prime})\delta n\left(\mathbf{r}^{\prime};\{\mathbf{R}_{0}\}\right), \quad (A41)\]  

where \(f_{\mathrm{xc}}(\mathbf{r},\mathbf{r}^{\prime}) = f_{\mathrm{xc}}(\mathbf{r})\delta_{\mathbf{r} - \mathbf{r}^{\prime}} = \left.\frac{\partial V^{\mathrm{xc}}[n]}{\partial n}\right|_{n = n(\mathbf{r})}\delta_{\mathbf{r} - \mathbf{r}^{\prime}}\) was the exchange correlation kernel in LDA.  

The density deviation is proportional to the Kohn- Sham potential deviation,  

\[\delta n\left(\mathbf{r};\{\mathbf{R}_{0}\}\right) = \int_{\mathbf{r}^{\prime}}\chi_{0}^{\mathrm{e}}\left(\mathbf{r},\mathbf{r}^{\prime}\right)\delta V^{\mathrm{KS}}\left(\mathbf{r}^{\prime};\{\mathbf{R}_{0}\}\right) \quad (A42)\]  

where \(\chi_{0}^{\mathrm{e}}\) is the density- density correlation of free electrons. Without interaction, we have \(\chi_{0}^{\mathrm{e}} = P^{(0)}\) , the polarization of free electrons, given by the Lindhard function. We then symbolically have  

\[\delta V^{\mathrm{KS}} = \frac{1}{1 - (v + f_{\mathrm{xc}})\chi_{0}^{\mathrm{e}}}\delta V^{\mathrm{ion}}, \quad (A43)\]  

where both \(v\) and \(f_{\mathrm{xc}}\) are functions of \(\mathbf{r},\mathbf{r}^{\prime}\) , and their multiplication to \(\chi_{0}^{\mathrm{e}}\) and inverse correspond to convolution and inverse of functions. If we further assume that the density of electrons varies slowly in space, we have \(f_{\mathrm{xc}}(\mathbf{r})\approx f_{\mathrm{xc}}\) , and then the Fourier transformed counterpart of this equation became algebraic.



Now the electron-phonon interaction,  

\[g_{i\alpha}^{\mathrm{KS}}(\mathbf{r})\equiv \frac{\partial V^{\mathrm{KS}}(\mathbf{r};\{\mathbf{R}\})}{\partial R_{i\alpha}}\bigg|_{\mathbf{R} = \mathbf{R}_{0}}, \quad (A44)\]  

as defined in DFPT, could be expressed as  

\[g^{\mathrm{KS}} = \frac{g^{0}}{1 - (v + f_{\mathrm{xc}})\chi_{0}^{6}} \quad (A45)\]  

where \(g^{0} = v_{\mathbf{q}}g^{\mathrm{r}}\) . By observing that in LDA  

\[\chi^{\mathrm{e}}(\mathbf{q}) = \frac{P_{\mathbf{q}}}{1 - v_{\mathbf{q}}P_{\mathbf{q}}}\approx \frac{\chi_{0}^{\mathrm{e}}}{1 - (v + f_{\mathrm{xc}})\chi_{0}^{\mathrm{e}}}, \quad (A46)\]  

we have  

\[g^{\mathrm{KS}}\approx g^{\mathrm{r}}v_{\mathbf{q}}\frac{\chi^{\mathrm{e}}(\mathbf{q})}{\chi_{0}^{\mathrm{e}}(\mathbf{q})}. \quad (A46)\]  

Then we could see that the quality of this approximation was determined by the difference between \(v_{\mathbf{q}}\frac{\chi^{\mathrm{e}}(\mathbf{q})}{\chi_{0}^{\mathrm{e}}(\mathbf{q})}\) and \(z^{\mathrm{e}}W_{\mathbf{q}}\Gamma_{3}^{\mathrm{e}}(\mathbf{k};\mathbf{q})\) by comparing \(g^{\mathrm{KS}}\) with its many- body counterpart \(g = g^{\mathrm{r}}(z^{\mathrm{e}}W^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}})\) , as pointed out in Eq.(34).  

## Appendix B: Pair-field BSE  

This section details the derivation of the BSE for the anomalous vertex, which governs PCF. We employ the Nambu- Gor'kov formalism, defining the Nambu spinors as:  

\[\bar{\Psi} = (\bar{\psi}_{\uparrow},\psi_{\downarrow}),\quad \Psi = \binom{\psi_{\uparrow}}{\psi_{\downarrow}}. \quad (B1)\]  

We consider the system at \(T > T_{c}\) with a source term,  

\[S[\hat{\eta}] = S + \int_{12}\bar{\Psi}_{1}\hat{\eta}_{12}\Psi_{2} + h.c.\quad , \quad (B2)\]  

where the subscript \(i\) abbreviates \((\mathbf{r}_{i},\tau_{i})\) . The source term matrix is  

\[\hat{\eta}_{12} = \left[ \begin{array}{cc}\eta_{12} & \eta_{12}^{a}\\ (\eta_{12}^{a})^{*} & -\eta_{21} \end{array} \right], \quad (B3)\]  

introducing a normal source term \(\eta\) and an anomalous source term \(\eta^{a}\) . These modify the bare electron propagator's inverse: \(\hat{g}_{12}^{- 1}[\hat{\eta}] = \mathrm{diag}(g_{12}^{- 1}, - g_{21}^{- 1}) + \hat{\eta}_{12}\) .  

The full Green's function is defined as  

\[\hat{G}_{12}\equiv -\langle \Psi_{1}\bar{\Psi}_{2}\rangle \equiv \left[ \begin{array}{cc}G_{12} & F_{12}\\ F_{12}^{*} & -G_{21} \end{array} \right], \quad (B4)\]  

where \(G\) is the normal and \(F\) is the anomalous (Gorkov) Green's function. These can be obtained by functional derivatives of the partition function:  

\[G_{12}[\eta ,\eta^{\mathrm{a}}] = \frac{\delta\ln Z[\eta ,\eta^{\mathrm{a}}]}{\delta\eta_{12}},\quad F_{12}[\eta ,\eta^{\mathrm{a}}] = \frac{\delta\ln Z[\eta ,\eta^{\mathrm{a}}]}{\delta\eta_{12}^{\mathrm{a}}}. \quad (B5)\]  

We retain the source terms in the Green's functions, keeping zeroth order for \(G\) and first order for \(F\) through the derivation. The physical quantities are obtained by setting the sources to zero at the end.  

The Nambu self- energy is defined as \(\hat{\Sigma}_{12} = \hat{G}_{12}^{- 1} - \hat{g}_{12}^{- 1}\) . This yields a matrix equation that expands into two coupled Dyson's equations for the normal and anomalous Green's functions. At \(T > T_{c}\) , these equations decouple in the leading order, resulting in \(\Sigma = G^{- 1} - g^{- 1} + O(\eta ,\eta^{\mathrm{a}})\) and \(\Sigma^{\mathrm{a}} = G^{- 1}FG^{- 1}\) .  

We define the element- wise functional derivative of a Nambu matrix \(\hat{A}\) with respect to the Nambu source matrix \(\hat{\eta}\) as:  

\[\frac{\delta\hat{A}}{\delta\hat{\eta}_{12}} = \left[ \begin{array}{cc}\frac{\delta A}{\delta\eta_{12}} & \frac{\delta A^{\mathrm{a}}}{\delta\eta_{12}^{\mathrm{a}}}\\ \frac{\delta(A^{\mathrm{a}})^{*}}{\delta(\eta_{12}^{\mathrm{a}})^{*}} & -\frac{\delta A}{\delta\eta_{21}} \end{array} \right]. \quad (B6)\]  

Applying this definition to the functional derivative of the inverse Green's function yields:  

\[\frac{\delta\hat{G}_{12}^{-1}}{\delta\hat{\eta}_{33}}\bigg|_{\hat{\eta} = 0} = \left[ \begin{array}{c}\Gamma_{12,3}^{3}\\ (\Lambda_{12,3})^{*} \end{array} \right.\frac{\Lambda_{12,3}}{\Gamma_{21,3}^{3}}, \quad (B7)\]  

where \(\Gamma^{3}\) is the normal three- point vertex and \(\Lambda\) is the anomalous three- point vertex.  

Now we derive the BSE for \(\Lambda\) . Starting with the relation \(\hat{G}_{12}^{- 1} = \hat{g}_{12}^{- 1} + \hat{\Sigma}_{12}\) and using the functional derivative relation \(\frac{\delta\hat{G}}{\delta\hat{\eta}} = -\hat{G}\frac{\delta\hat{G}^{- 1}}{\delta\hat{\eta}}\hat{G}\) , we obtain from the off- diagonal components:  

\[\begin{array}{c}{\Lambda_{12,3} = \delta_{13}\delta_{23} + \frac{\delta\Sigma_{12}^{a}}{\delta\eta_{33}^{a}}}\\ {= \delta_{13}\delta_{23} + \int_{45}\frac{\delta\Sigma_{12}^{a}}{\delta F_{45}} G_{44^{\prime}}G_{55^{\prime}}\Lambda_{4^{\prime}5^{\prime};3}^{a}.} \end{array} \quad (B8)\]  

Here, the functional derivative of \(\Sigma^{\mathrm{a}}\) with respect to \(F\) yields the particle- particle irreducible four- point vertex function \(\bar{\Gamma}_{14;25} = \frac{\delta\Sigma_{12}}{\delta F_{45}}\) . This equation for \(\Lambda\) gives the desired Bethe- Salpeter equation, solvable self- consistently given \(G\) and \(\bar{\Gamma}\) .  

## Appendix C: Finite Temperature Scaling: Generic BCS  

We started by writing the Eq.(B8) explicitly without phonons:  

\[\Lambda_{\mathbf{k}\omega} = 1 + \int_{\mathbf{k}^{\prime}\omega^{\prime}}\bar{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\Lambda_{\mathbf{k}^{\prime}\omega^{\prime}}, \quad (C1)\]  

where we set the source term \(\eta \equiv 1\) . The vertex \(\bar{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\) is exempt from Cooper singularities, and connects to the full vertex function via the self- consistent equation:  

\[\Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \bar{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} + \int_{\mathbf{k}^{\prime\prime}\omega^{\prime \prime}}\bar{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime \prime}\omega^{\prime \prime}}\Pi_{\mathbf{k}^{\prime \prime}\omega^{\prime \prime}}\Gamma_{\mathbf{k}^{\prime \prime}\omega^{\prime \prime};\mathbf{k}^{\prime}\omega^{\prime}}, \quad (C2)\]



where the \(\Pi_{\mathbf{k}\omega}\) is the quasiparticle pair- field propagator.  

The source term \(\eta_{\mathbf{k}\omega}\) is a smooth function of \(\mathbf{k}\omega\) that we normally set to unity in real calculations, and \(\Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \Gamma (\mathbf{k},\omega , - \mathbf{k},\omega ;\mathbf{k}^{\prime},\omega^{\prime}, - \mathbf{k}^{\prime},\omega^{\prime})\) is the full four- point vertex function that can be derived from the connected two- electron Green's function.  

As first illustrated in Ref. [25], for emergent BCS superconductors and non- superconductors at the Fermi surface, the linear response function follows a universal scaling relation, which we call precursory Cooper flow (PCF):  

\[\Lambda_{0}(T) = \frac{1}{1 + g\ln(\omega_{\Lambda} / T)} +\mathcal{O}(T), \quad (C3)\]  

Here the label 0 represents the low- energy limit \(|\mathbf{k}| = k_{\mathrm{F}}\) , \(\omega = \pi T\) , which we denote by \(\mathbf{k}\omega = 0\) . Consequently, one can estimate the critical temperature \(T_{\mathrm{c}}\) as \(T_{\mathrm{c}} \equiv \omega_{\Lambda}e^{- 1 / g}\) by computing \(\Lambda_{0}(T)\) at temperatures well above the superconducting state. This methodology circumvents the need to perform calculations within the challenging superconducting regime, offering a more practical and robust predictive tool. The goal of this section is to derive this universal scaling and its prerequisite.  

## 1 Singularity Analysis  

For a generic electron system, the BCS pairing originates from \(\Pi_{\mathbf{k}\omega} = G_{\mathbf{k}\omega}G_{- \mathbf{k}\omega}\) , where \(G_{\mathbf{k}\omega}\) is the electron Green's function  

\[G_{\mathbf{k}\omega} = \frac{z}{-i\omega + \epsilon_{\mathbf{k}}} +\mathrm{reg} \quad (C4)\]  

Here \(\epsilon_{\mathbf{k}} = \mathbf{v}_{\mathrm{F}}^{*}\cdot (\mathbf{k} - \mathbf{k}_{\mathrm{F}})\) is the quasi- particle dispersion, \(z\) is the fermi liquid renormalization factor, and \(v_{\mathrm{F}}^{*}\) is the renormalized fermi velocity. The first term is the leading contribution of taylor expansion of the exact dispersion around Fermi surface. The corrections lead to a regular contribution that saturates to a constant at \(\mathbf{k}\omega = 0\) . Below we denote such terms as reg.  

The same separation applies to \(\Pi_{\mathbf{k}\omega}\)  

\[\Pi_{\mathbf{k}\omega} = \frac{z^{2}}{\omega^{2} + \epsilon_{\mathbf{k}}^{2}} +\mathrm{reg} \quad (C5)\]  

It immediately follows that  

\[\int_{\mathbf{k}\omega}\Pi_{\mathbf{k}\omega} = A\ln T + B + \mathcal{O}(T) \quad (C6)\]  

where \(A = \frac{z^{2}\pi}{2v_{\mathrm{F}}}\) and \(B\) are two constants, and the finite- temperature correction \(\mathcal{O}(T)\) vanishes as power series of \(T\) . This low- energy singularity has been thoroughly studied in the BCS theory.  

Another singular property comes from dynamical screened Coulomb interaction in the irreducible vertex \(\tilde{\Gamma}\) . As revealed in the random phase approximation (RPA), only the static part of Coulomb interaction is  

fully screened. For any transfer frequency \(\omega - \omega^{\prime}\neq 0\) it remains long range with a plasmon contribution \(W^{s}\) that diverges when transfer momentum \(\mathbf{q} = \mathbf{k} - \mathbf{k}^{\prime}\) goes to zero. Therefore, we adopt the following separation of irreducible vertex  

\[\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}} + W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{\mathrm{s}} \quad (C7)\]  

Since the parametrization of \(W^{s}\) remains non- unique, provided it accurately captures the singularity, we choose the following simple form:  

\[W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{s} = \frac{4\pi e^{2}}{|\mathbf{k} - \mathbf{k}^{\prime}|^{2}}\frac{(\omega - \omega^{\prime})^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{p}^{2}}. \quad (C8)\]  

Here \(\omega_{\mathrm{p}}\) is the characteristic plasma frequency. This singular contribution was ignored by the conventional treatment, where Coulomb pseudopotential only takes into account the static interaction. In the next section, we will demonstrate the Coulomb singularity does not change the universal temperature scaling in PCF.  

## 2 Temperature Scaling of the PCF  

Without loss of generality, we focus on the isotropic case, where all functions in the equations could be decomposed with spherical harmonics. The results could be extended to the cases where anisotropy of the system is not extreme. If, on the other hand, the system shows drastic behavior, for instance some singularity of dispersion at certain symmetry points on the Fermi surface, then there is no guarantee the results persist, and the derivation should be re- examined carefully.  

To simplify the notation, we first introduce a symbolic expression of Eq.(C1)  

\[\Lambda = \frac{1}{1 + \tilde{\Gamma}\Pi} I \quad (C9)\]  

Here \(I_{\mathbf{k}^{\prime}\omega^{\prime}} = 1\) is an uniform function of \(\mathbf{k}^{\prime}\omega^{\prime}\) , and \(\tilde{\Gamma}\Pi\) should be considered as an operator that follows  

\[\tilde{\Gamma}\Pi X = \int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}X_{\mathbf{k}^{\prime}\omega^{\prime}} \quad (C10)\]  

where \(X_{\mathbf{k}^{\prime}\omega^{\prime}}\) is the function that this operator acts on. Pay attention that (i) The operators do not commute with each other, thus it is important to keep their order the same as in the original equation; (ii) Any function of symbolic operators should be treated as a taylor expansion. For example \(1 / (1 + X)\) in above equations represents a geometric series \(\delta + \sum_{n = 1}^{\infty}X^{n}\) , where the identity matrix \(\delta\) is defined by  

\[\delta = \delta_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}} = \frac{1}{T}\delta_{\omega -\omega^{\prime}}\delta_{\mathbf{k} - \mathbf{k}^{\prime}}, \quad (C11)\]  

so that \(\int_{\mathbf{k}^{\prime}\omega^{\prime}}\delta_{\mathbf{k}\omega -\mathbf{k}^{\prime}\omega^{\prime}}X_{\mathbf{k}^{\prime}\omega^{\prime}} = X_{\mathbf{k}\omega}\) .



For an emergent BCS system that satisfies Eq.(C1), \(\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\) must be free of singularity at \(\mathbf{k}^{\prime}\omega^{\prime} = 0\) that is strong enough to alter the \(\ln T\) dependence. In first order, this condition could be rigorously formulated as  

\[\int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}} = \tilde{g}_{\mathbf{k}\omega}\ln T + \tilde{f}_{\mathbf{k}\omega} + \mathcal{O}(T), \quad (C12)\]  

which guarantees that no singular term beyond \(\ln T\) is generated. In the following we show that as long as the temperature- independent functions \(\tilde{g}_{\mathbf{k}\omega}\) and \(\tilde{f}_{\mathbf{k}\omega}\) are regular in the \(\mathbf{k}\omega \rightarrow 0\) limit, the singular \(\ln T\) terms at higher order automatically follows a simple geometric series.  

To see this, we first consider the second order term  

\[\tilde{\Gamma}\Pi \tilde{\Gamma}\Pi = \int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}(\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}}\ln T + \tilde{f}_{\mathbf{k}^{\prime}\omega^{\prime}}) + \mathcal{O}(T) \quad (C13)\]  

Since \(\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}}\) and \(\tilde{f}_{\mathbf{k}^{\prime}\omega^{\prime}}\) are regular at \(\mathbf{k}^{\prime}\omega^{\prime}\rightarrow 0\) and independent of \(\mathbf{k}\omega\) , they do not change the singular structure of \(\tilde{\Gamma}\Pi\) , meaning that  

\[\int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}} = \tilde{g}_{\mathbf{k}\omega}^{\prime}\ln T + \tilde{f}_{\mathbf{k}\omega}^{\prime} + \mathcal{O}(T) \quad (C14)\]  

where \(\tilde{g}_{\mathbf{k}\omega}^{\prime}\) and \(\tilde{f}_{\mathbf{k}\omega}^{\prime}\) are also regular at \(\mathbf{k}^{\prime}\omega^{\prime}\rightarrow 0\) . Invoking the mathematical induction, we find that only one \(\ln T\) singular contribution is generated when the order increases by one.  

The above observation enables us to determine whether the system is emergent BCS by checking the validity of Eq.(C12). It also allows us to extract the renormalized constants in Eq.(C3) by defining  

\[\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}} = \left[\tilde{g}_{\mathbf{k}\omega}\ln T + \tilde{f}_{\mathbf{k}\omega}\right]\delta_{\mathbf{k}^{\prime}\omega^{\prime}} + \phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} \quad (C15)\]  

where \(\int_{\mathbf{k}^{\prime}\omega^{\prime}}\phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \mathcal{O}(T)\) . We start by resumming the regular terms of \(\Lambda_{\mathbf{k}\omega}\) using the symbolical expression. First, we insert Eq.(C15) into Eq.(C9) (notice the operator nature of denominators):  

\[\begin{array}{l}{\Lambda = \frac{1}{1 + \phi + (\tilde{g}\ln T + \tilde{f})\delta} I}\\ {= \frac{1}{(1 + \phi)\left(1 + \frac{1}{1 + \phi} (\tilde{g}\ln T + \tilde{f})\delta\right)} I}\\ {= \frac{1}{1 + \frac{1}{1 + \phi} (\tilde{g}\ln T + \tilde{f})\delta}\frac{1}{1 + \phi} I}\\ {= \frac{1}{1 + \gamma (\tilde{g}\ln T + \tilde{f})\delta}\gamma I} \end{array} \quad (C16)\]  

where we have introduced  

\[\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \delta_{\mathbf{k}\omega -\mathbf{k}^{\prime}\omega^{\prime}} - \int_{\mathbf{k}^{\prime}\omega^{\prime}}^{\prime}\phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\gamma_{\mathbf{k}^{\prime}\omega^{\prime\prime}}\gamma_{\mathbf{k}^{\prime}\omega^{\prime\prime}};\mathbf{k}^{\prime}\omega^{\prime}. \quad (C17)\]  

Returning to Eq.(C16) with its explicit form, we find  

\[\Lambda_{\mathbf{k}\omega} = 1 - \int_{\mathbf{k}^{\prime}\omega^{\prime}}\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\left(\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}}\ln T + \tilde{f}_{\mathbf{k}^{\prime}\omega^{\prime}}\right)\Lambda_{0} + \mathcal{O}(T) \quad (C18)\]  

where we have used \(\int_{\mathbf{k}^{\prime}\omega^{\prime}}\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = 1 + \mathcal{O}(T)\) that follows \(\int_{\mathbf{k}^{\prime}\omega^{\prime}}\phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} = \mathcal{O}(T)\) . Defining  

\[g_{\mathbf{k}\omega} = -\int_{\mathbf{k}^{\prime}\omega^{\prime}}\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}},\quad f_{\mathbf{k}\omega} = -\int_{\mathbf{k}^{\prime}\omega^{\prime}}\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\tilde{f}_{\mathbf{k}^{\prime}\omega^{\prime}} \quad (C19)\]  

we can solve the algebraic equation at \(\mathbf{k}\omega = 0\) , which immediately recovers the key result Eq.(C3) with \(g = g_{0}\) , \(f = f_{0}\) and \(\omega_{\Lambda} = e^{- \frac{f_{0}}{g_{0}}}\) for its coefficients.  

We also immediately restore expression of \(\Lambda_{\mathbf{k}\omega}\) :  

\[\begin{array}{c}{\Lambda_{\mathbf{k}\omega} = \frac{1 + (g_{\mathbf{k}\omega} - g)\ln T + (f_{\mathbf{k}\omega} - f)}{1 - g\ln T - f}}\\ {= \frac{J_{\mathbf{k}\omega}}{1 + g\ln \frac{\omega_{\Lambda}}{T}} +1 - \frac{g_{\mathbf{k}\omega}}{g} +\mathcal{O}(T)}\\ {J_{\mathbf{k}\omega} = f_{\mathbf{k}\omega} + (1 - f)\frac{g_{\mathbf{k}\omega}}{g}} \end{array} \quad (C20)\]  

This final form shows that \(\Lambda_{\mathbf{k}\omega}\) is also regular at \(\mathbf{k}\omega = 0\) as directly inherited from \(g_{\mathbf{k}\omega}\) and \(f_{\mathbf{k}\omega}\) .  

Following the same derivation, we can also establish the temperature scaling of full vertex \(\Gamma\)  

\[\begin{array}{c}{\Gamma = \frac{1}{1 + \tilde{\Gamma}\Pi}\tilde{\Gamma}}\\ {= \frac{1}{1 + \gamma (\tilde{g}\ln T + \tilde{f})\delta}\gamma \tilde{\Gamma}} \end{array} \quad (C22)\]  

which can be rewritten explicitly as  

\[\begin{array}{l}{\Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} =}\\ {\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{*} - \int_{\mathbf{k}^{\prime}\omega^{\prime}}^{\prime}\gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\left(\tilde{g}_{\mathbf{k}^{\prime}\omega^{\prime}}\ln T + \tilde{f}_{\mathbf{k}^{\prime}\omega^{\prime}}\right)\Gamma_{0;\mathbf{k}^{\prime}\omega^{\prime}}}\\ {\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{*} = \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} - \int_{\mathbf{k}^{\prime}\omega^{\prime}}^{\prime}\phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}^{\prime}\omega^{\prime};\mathbf{k}^{\prime}\omega^{\prime}}^{*} \end{array} \quad (C23)\]  

Setting \(\mathbf{k}\omega = 0\) , we find  

\[\Gamma_{0;\mathbf{k}^{\prime}\omega^{\prime}} = \frac{\tilde{\Gamma}_{0;\mathbf{k}^{\prime}\omega^{\prime}}^{*}}{1 - g\ln T - f} \quad (C24)\]  

Notice that \(\tilde{\Gamma}^{*}\) does not have any \(\ln T\) scaling, as \(\phi\) in Eq.(C23) is a regular function.  

## 3 Emergent BCS of Dynamical Screened Coulomb interaction  

As we mentioned, the plasmon contribution \(W^{\mathrm{s}}\) in the screened Coulomb interaction diverges at \(\omega - \omega^{\prime}\neq 0\) ,



\(|\mathbf{k} - \mathbf{k}^{\prime}| = 0\) . Therefore, We have to verify that the \(\ln T\) divergence from \(\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\) is not changed by this additional singularity.  

In Eq.(C7), the first regular term \(\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}}\) is smooth at \(\mathbf{k}^{\prime}\omega^{\prime} = 0\) . Applying Eq.(C6), we can write  

\[\begin{array}{r l r} & {} & {\int_{\mathbf{k}^{\prime}\omega^{\prime}}\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}} = \int_{\mathbf{k}^{\prime}\omega^{\prime}}\left(\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}} - \tilde{\Gamma}_{\mathbf{k}\omega ;0}^{\mathrm{r}} + \tilde{\Gamma}_{\mathbf{k}\omega ;0}^{\mathrm{r}}\right)\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\\ & {} & {= A\tilde{\Gamma}_{\mathbf{k}\omega ;0}^{\mathrm{r}}\ln T + B\tilde{\Gamma}_{\mathbf{k}\omega ;0}^{\mathrm{r}} + \int_{\mathbf{k}^{\prime}\omega^{\prime}}\Delta \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}} \end{array} \quad (C25)\]  

where \(\Delta \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}} = \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}} - \tilde{\Gamma}_{\mathbf{k}\omega ;0}^{\mathrm{r}}\) vanishes as polynomials of \(|\mathbf{k}^{\prime}| - k_{\mathrm{F}}\) and \(\omega^{\prime}\) when \(\mathbf{k}^{\prime}\omega^{\prime}\to 0\) . This means the singularity of \(\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\) in the last term is cancelled by \(\Delta \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{r}}\) , yielding a regular function of \(\mathbf{k}\omega\) and \(T\) . Clearly all terms in Eq.(C25) are finite when \(\mathbf{k}\omega\) goes to zero, which satisfies the emergent BCS condition.  

The analysis of the second term \(W^{\mathrm{s}}\) is more tricky. For simplicity, we assume the Fermi surface is spherical, so that dispersion in Eq.(C4) reduces to scalar product \(v_{\mathrm{F}}^{*}(k^{\prime} - k_{\mathrm{F}})\) with no angle dependence. Integrating the angle dependence explicitly, we have  

\[\begin{array}{r l} & {\int_{\mathbf{k}^{\prime}\omega^{\prime}}W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{\mathrm{s}}\Pi_{\mathbf{k}^{\prime}\omega^{\prime}} =}\\ & {\int_{k^{\prime}\omega ,\chi}\frac{k^{\prime 2}}{\pi(k^{2} + k^{\prime 2} - 2k k^{\prime}\chi)}\frac{(\omega - \omega^{\prime})^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{p}^{2}}\frac{(z^{\mathrm{e}})^{2}}{\omega^{2} + \epsilon_{k^{\prime}}^{2}}}\\ & {= \int_{k^{\prime}\omega^{\prime}}(k_{\mathrm{F}} + \Delta k^{\prime})^{2}\frac{2e^{2}}{\pi}\ln \left|\frac{\Delta k - \Delta k^{\prime}}{2k_{\mathrm{F}} + \Delta k + \Delta p}\right|}\\ & {\times \frac{(\omega - \omega)^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{p}^{2}}\frac{(z^{\mathrm{e}})^{2}}{\omega^{2} + v_{\mathrm{F}}^{*2}\Delta k^{\prime 2}}} \end{array} \quad (C26)\]  

where \(\chi \in [- 1,1]\) and \(\Delta k^{\prime} = k^{\prime} - k_{\mathrm{F}}\) . The key observation is that singular region of \(W^{\mathrm{s}}\) and \(\Pi\) overlaps in the limit \(\Delta k\to 0\) , \(\Delta p\to 0\) , \(\omega_{n}\to 0\) . Therefore, the only contribution, omitting a constant factor \(k_{\mathrm{F}}^{2}z^{2}e^{2} / \pi\) , that could potentially break the emergent BCS condition is  

\[S_{k\omega} = \frac{\omega^{2}}{\omega^{2} + \omega_{p}^{2}}\int_{\Delta k^{\prime}\omega^{\prime}}\ln \left|\frac{\Delta k - \Delta k^{\prime}}{2k_{\mathrm{F}}}\right|\frac{1}{\omega^{\prime 2} + v_{\mathrm{F}}^{*2}\Delta k^{\prime 2}}\] \[\qquad = \frac{\omega^{2}}{\omega^{2} + \omega_{p}^{2}}\int_{\Delta k^{\prime}}\ln \left|\frac{\Delta k - \Delta k^{\prime}}{2k_{\mathrm{F}}}\right|\frac{\tanh(\frac{\epsilon}{2T})}{\epsilon}\]  

Here \(\epsilon = v_{\mathrm{F}}^{*}\Delta k^{\prime}\) , and we explicitly sum over \(\omega^{\prime}\) . The \(\tanh (\frac{\epsilon}{2T})\) is equivalent to introducing an infrared cutoff \(T / v_{\mathrm{F}}\) to momentum integral. In the low- energy limit \(k\omega \to 0\) , the momentum integral yields  

\[\lim_{k\omega \to 0}S_{k\omega} = \frac{\pi^{2}T^{2}}{\pi^{2}T^{2} + \alpha^{2}\omega_{p}^{2}}\ln \frac{p_{c}T}{4k_{\mathrm{F}}v_{\mathrm{F}}^{*}}\ln \frac{p_{c}v_{\mathrm{F}}^{*}}{T}\]  

Here \(p_{\mathrm{c}}\) is the momentum UV cutoff. This term vanishes as \((T\ln T)^{2}\) when \(T\) approaches zero. Therefore it does not break the emergent BCS condition. The dynamic structure of \(\tilde{\Gamma}^{\mathrm{s}}\) is crucial here, since it regularizes the \((\ln T)^{2}\) dependence that originates from the singular behavior of Coulomb interaction at small transfer momentum \(q\) .  

## Appendix D: Finite Temperature Scaling: Electron-Phonon BCS  

Since the electron- phonon interaction is a regular function in both momentum and frequency, the PCF temperature scaling we derived for generic cases applies to systems where screened Coulomb and electron- phonon interactions are equally important. In this section, we discuss how to simplify the PCF, taking advantage of the separation of energy scales in electron- phonon systems.  

The key observation is that, in most simple metals with moderate \(r_{\mathrm{s}}\) ranges between \(1\sim 5\) , the characteristic energy of phonon and plasmon are well separated. The plasmon frequency \(\omega_{\mathrm{p}}\) is of the same order of magnitude as the Fermi energy \(E_{\mathrm{F}}\) , while the Debye frequency \(\omega_{\mathrm{D}}\) of phonons is generally two orders of magnitude smaller than \(E_{\mathrm{F}}\) . Below we aim to show, without further assuming the details of the model, that the high energy part of the PCF equation above a cut- off frequency \(\omega_{\mathrm{c}}\) , which is chosen between the two characteristic frequencies \(\omega_{\mathrm{D}}\ll \omega_{\mathrm{c}}\ll \omega_{\mathrm{p}}\) , could be integrated out up to the accuracy of two small parameters, \(\eta_{\mathrm{p}} = \omega_{\mathrm{c}} / \omega_{\mathrm{p}}\) and \(\eta_{\mathrm{e}} = \omega_{\mathrm{D}} / \omega_{\mathrm{c}}\) .  

## 1 Phonon effects on the vertices of Quasi-particles  

In this section, we discuss the effects of phonon- mediated interaction on the Green's function and vertices under the assumption that \(\omega_{\mathrm{D}} / E_{\mathrm{F}}\ll 1\) and that the electron part is already solved. The electron properties relevant to our discussion are the quasi- particle Green's function  

\[G_{\mathbf{k}\omega}^{\mathrm{e}} = \frac{z^{\mathrm{e}}}{-i\omega + \epsilon_{\mathbf{k}}} +\mathrm{reg} \quad (D1)\]  

and the improper 3- vertex function  

\[\Gamma_{\mathbf{k}\omega ;\mathbf{q}\nu}^{\mathrm{3e}} = \frac{1}{z^{\mathrm{e}}}\frac{1}{1 - (v_{\mathbf{q}} + f_{\mathbf{q}}^{\mathrm{xc}})\Pi_{\mathbf{q}\nu}^{\mathrm{0}}} +\mathrm{reg}, \quad (D2)\]  

Here \(\epsilon_{\mathbf{k}} = \mathbf{v}_{\mathrm{F}}^{\mathrm{e}}\cdot (\mathbf{k} - \mathbf{k}_{\mathrm{F}})\) is the quasiparticle dispersion of electrons, \(\Pi_{0}\) is the frequency- momentum Lindhard function with the mass \(m^{*}\) , \(f_{\mathbf{q}}^{\mathrm{xc}}\) is the exchange- correlation kernel, \(q\) is the transfer frequency- momentum, and \(k\) is the frequency- momentum of the incoming electron.  

These functions can be prepared from first- principle calculation of UEG without phonons. The phonon effects, then, could be included in a simplified way according to the Migdal's theorem, as long as we only concerns about them up to \(O(\omega_{\mathrm{D}} / E_{\mathrm{F}})\) accuracy.  

We start by considering the phonon- induced interaction between quasi- particles that enters the particle- particle irreducible vertex \(\tilde{\Gamma}\)  

\[\tilde{\Gamma} = \tilde{\Gamma}^{\mathrm{e}} + W_{\mathrm{ph}} + O(m / M) \quad (D3)\]  

\[W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime};\mathbf{q}\nu}^{\mathrm{ph}} = \Gamma_{\mathbf{k}\omega ;\mathbf{q}\nu}^{\mathrm{3e}}g_{\mathbf{q}}D_{\kappa}(\mathbf{q},\nu)g_{\mathbf{q}}\Gamma_{\mathbf{k}^{\prime}\omega^{\prime};\mathbf{q}\nu}^{\mathrm{3e}}. \quad (D4)\]



Notice that as discussed in previous sections, the phonon propagator already includes the full electron density-density correlation \(\chi_{\mathrm{nn}}\) , thus no additional resummation over bubble diagrams is required in this form. Also, the 3- vertex includes no phonon correction, as dictated by Migdal's theorem.  

Next, we parametrize the phonon modification to the quasi- particle Green's function Eq. (D1). As demonstrated in Ref(PHONON- SELFENERGY), the changes to dispersion \(\epsilon_{\mathbf{k}}\) and Fermi velocity \(v_{\mathrm{F}}^{\mathrm{s}}\) are of order \(\mathcal{O}(m / M)\) , which gives  

\[G_{\mathbf{k}\omega} = \frac{z^{\mathrm{e}}}{-i\omega / z_{\omega}^{\mathrm{ph}} + \epsilon_{\mathbf{k}}} +O(\eta_{\mathrm{e}}) + \mathrm{reg}, \quad (D5)\]  

Here \(z_{\omega}^{\mathrm{ph}}\) is the frequency dependent factor obtained from analysing the first order corrections of self- energy by \(W_{\mathrm{ph}}\) .  

## 2 4-vertex and pseudo-potential  

With \(\tilde{\Gamma}\) parametrized as Eq. (D3), the PCF equation of the electron- phonon problem can be expressed as:  

\[\Lambda_{\mathbf{k}\omega} = I_{\mathbf{k}\omega} + \int_{\mathbf{k}^{\prime}\omega^{\prime}}(\tilde{\Gamma}_{\mathbf{k}\omega ,\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}} + W_{\mathbf{k}\omega ,\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}})\Pi_{\mathbf{k}^{\prime}\omega^{\prime}}\Lambda_{\mathbf{k}^{\prime}\omega^{\prime}} + O(\eta_{\mathrm{e}}), \quad (D6)\]  

where \(I_{\mathbf{k}\omega} \equiv 1\) is the source term. Starting from this point, variables and internal integrals are again omitted for brevity, wherever context permits. The above equation can be rewritten as,  

\[\Lambda = I + (\tilde{\Gamma}^{\mathrm{e}} + W^{\mathrm{ph}})\Pi \Lambda +O(\eta_{\mathrm{e}}). \quad (D7)\]  

We replace the electron irreducible vertex function with the electron full vertex function,  

\[\Gamma^{\mathrm{e}} = \tilde{\Gamma}^{\mathrm{e}} + \tilde{\Gamma}^{\mathrm{e}}\Pi^{\mathrm{e}}\Gamma^{\mathrm{e}}, \quad (D8)\]  

where \(\Pi^{\mathrm{e}}\) is the pair- field propagator without phonon. We obtain  

\[\Lambda = I + \Gamma^{\mathrm{e}}\Pi^{\mathrm{e}}I + \Gamma^{\mathrm{e}}\delta \Pi \Lambda +(1 + \Gamma^{\mathrm{e}}\Pi^{\mathrm{e}})W^{\mathrm{ph}}\Pi \Lambda +O(\eta_{\mathrm{e}}), \quad (D9)\]  

where \(\delta \Pi = \Pi - \Pi^{\mathrm{e}}\) .  

In the equation above, the first two terms collectively represent the PCF for the pure electron liquid, denoted as \(\Lambda^{\mathrm{e}} = I + \Gamma^{\mathrm{e}}\Pi^{\mathrm{e}}I\) . The above equation can be formally expressed as:  

\[\Lambda = \Lambda^{\mathrm{e}} + \Gamma^{\mathrm{e}}\delta \Pi \Lambda +(1 + \Gamma^{\mathrm{e}}\Pi^{\mathrm{e}})W^{\mathrm{ph}}\Pi \Lambda +O(\eta_{\mathrm{e}}), \quad (D10)\]  

Here, the electron liquid PCF \(\Lambda^{\mathrm{e}}\) serves as the source term that is subsequently modified by the electron- phonon interactions to yield the full electron- phonon PCF \(\Lambda\) .  

We first define the low- energy part of the pair- field propagator. Turning off the electron- phonon coupling, the low- energy pair- field propagator is defined by,  

\[\Pi_{\mathbf{k},\omega}^{\mathrm{e},\mathrm{s}}\equiv \frac{(z^{\mathrm{e}})^{2}}{\omega^{2} + \epsilon_{\mathbf{k}}^{2}}\Theta (\omega_{\mathrm{c}} - |\epsilon_{\mathbf{k}}|), \quad (D11)\]  

The electron- phonon coupling renormalizes the low- energy pair- field propagator into,  

\[\Pi_{\mathbf{k},\omega}^{\mathrm{s}}\equiv \frac{(z^{\mathrm{e}})^{2}}{\left(\frac{\omega}{z_{\omega}^{\mathrm{ph}}}\right)^{2} + \epsilon_{\mathbf{k}}^{2}}\Theta (\omega_{\mathrm{c}} - |\epsilon_{\mathbf{k}}|), \quad (D12)\]  

where the weight \(z_{\omega}^{\mathrm{ph}}\) approaches to one above the Debye frequency \(\omega_{\mathrm{D}}\) , reducing Eq. (D12) to Eq. (D11).  

The low- energy difference of the pair- field propagator due to the phonon- induced correction, is then  

\[\begin{array}{r l} & {\delta \Pi_{\mathbf{k},\omega}^{\mathrm{s}} = \Pi_{\mathbf{k},\omega}^{\mathrm{s}} - \Pi_{\mathbf{k},\omega}^{\mathrm{e},\mathrm{s}}}\\ & {\qquad = \frac{(z^{\mathrm{e}})^{2}\left(\frac{1}{z_{\omega}^{\mathrm{ph}}} - 1\right)\omega^{2}}{(\omega^{2} + \epsilon_{\mathbf{k}}^{2})\left(\left(\frac{\omega}{z_{\omega}^{\mathrm{ph}}}\right)^{2} + \epsilon_{\mathbf{k}}^{2}\right)}\Theta (\omega_{\mathrm{c}} - |\epsilon_{\mathbf{k}}|).} \end{array} \quad (D13)\]  

where the weight \(z_{\omega}^{\mathrm{ph}}\) approaches to one above the Debye frequency \(\omega_{\mathrm{D}}\) , introducing a frequency cutoff to \(\delta \Pi\) .  

Consider two functions \(A_{\mathbf{k}\omega}\) and \(B_{\mathbf{k}\omega}\) that are regular functions of the momentum near the Fermi surface below the scale of \(\omega_{\mathrm{D}} / v_{\mathrm{F}}^{\mathrm{e}}\) . Then we can prove two equations,  

\[\int_{\mathbf{k}\omega}A_{\mathbf{k}\omega}\Pi_{\mathbf{k}\omega}W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} = \int_{\mathbf{k}\omega}A_{\mathbf{k}\mathbf{F}\omega}\Pi_{\mathbf{k}\omega}^{\mathrm{s}}W_{\mathbf{k}\mathbf{F}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} + O(\eta_{\mathrm{e}}), \quad (D14)\]  

and  

\[\int_{\mathbf{k}\omega}A_{\mathbf{k}\omega}\delta \Pi_{\mathbf{k}\omega}B_{\mathbf{k}\omega} = \int_{\mathbf{k}\omega}A_{\mathbf{k}\mathbf{F}\omega}\delta \Pi_{\mathbf{k}\omega}^{\mathrm{s}}B_{\mathbf{k}\mathbf{F}\omega} + O(\eta_{\mathrm{e}}), \quad (D15)\]  

The proof of Eq. (D14) follows two steps:  

First, we prove the following equation,  

\[\int_{\mathbf{k}\omega}A_{\mathbf{k}\omega}\Pi_{\mathbf{k}\omega}W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} = \int_{\mathbf{k}\omega}A_{\mathbf{k}\omega}\Pi_{\mathbf{k}\omega}^{\mathrm{s}}W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} + O(\eta_{\mathrm{e}}) \quad (D16)\]  

The phonon propagator \(W^{\mathrm{ph}}\) imposes a UV frequency cutoff \(\omega_{\mathrm{D}}\) to the internal frequency \(\omega\) . As a result, the total contribution is suppressed by the small parameter \(\eta_{\mathrm{e}}\) .  

Consider the renormalized phonon propagator,  

\[W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}}\equiv \frac{\omega_{\mathbf{k} - \mathbf{k}^{\prime}}^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathbf{k} - \mathbf{k}^{\prime}}^{2}}\leq \frac{\omega_{\mathrm{D}}^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathrm{D}}^{2}}, \quad (D17)\]  

where we assume that the phonon dispersion is upper bounded by the Debye frequency \(\omega_{\mathbf{k} - \mathbf{k}^{\prime}}\leq \omega_{\mathrm{D}}\) .  

We show that any bounded and absolutely integrable function \(\psi_{\mathbf{k}\omega}\) convoluted with the phonon propagator is



of the order \(O(\eta_{\mathrm{e}})\) ,  

\[\begin{array}{r l r} & {} & {\left|\int_{\omega \mathbf{k}} \psi_{\mathbf{k}\omega} W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}}\right|\leq \int_{\omega \mathbf{k}} \frac{|\psi_{\mathbf{k}\omega}|\omega_{\mathrm{D}}^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathrm{D}}^{2}}}\\ & {} & {\qquad \leq \pi \omega_{\mathrm{D}}\sup_{\omega^{\prime \prime}} \int_{\mathbf{k}} |\psi_{\mathbf{k}\omega^{\prime \prime}}| = O(\eta_{\mathrm{e}})}\\ & {} & {\qquad \mathrm{We~then~observe~that}} \end{array} \quad (D18)\]  

We then observe that  

\[\Pi_{\mathbf{k}\omega} - \Pi_{\mathbf{k}\omega}^{\mathrm{s}} = \frac{(z^{\mathrm{e}})^{2}}{\left(\frac{\omega}{z_{\omega}^{\mathrm{ph}}}\right)^{2} + \epsilon_{\mathbf{k}}^{2}}\Theta (\epsilon_{\mathbf{k}} - \omega_{\mathrm{c}}) + \mathrm{reg} \quad (D19)\]  

is a bounded function that satisfies Eq. (D18). Therefore, replacing \(\Pi_{\mathbf{k}\omega}\) with \(\Pi_{\mathbf{k}\omega}^{\mathrm{s}}\) only leads to corrections of the order \(O(\eta_{\mathrm{e}})\) , as written in Eq. (D16).  

We further prove  

\[\int_{\mathbf{k}\omega}A_{\mathbf{k}\omega}\Pi_{\mathbf{k}\omega}^{\mathrm{s}}W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} = \int_{\mathbf{k}\omega}A_{\mathbf{k}\mathbf{F}\omega}\Pi_{\mathbf{k}\omega}^{\mathrm{s}}W_{\mathbf{k}\mathbf{F}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}} + O(\eta_{\mathrm{e}}). \quad (D20)\]  

Consider the first order corrections from the momentum dependence of \(A\) and \(W^{\mathrm{ph}}\) . We assume that  

\[A_{\mathbf{k}\omega} = A_{\omega}^{(0)} + \mathbf{A}_{\omega}^{(1)}\cdot \delta \mathbf{k} / k_{\mathrm{F}} + O(|\delta \mathbf{k}|^{2} / k_{\mathrm{F}}^{2}), \quad (D21)\]  

and similar relation for \(W^{\mathrm{ph}}\) . Then the leading correction is  

\[\begin{array}{r l} & {\left|\int_{\mathbf{k}\omega}(\mathbf{A}_{\omega}^{(1)}\cdot \delta \mathbf{k} / k_{\mathrm{F}})\Pi_{\mathbf{k}\omega}^{\mathrm{ph}}W_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{ph}}\right|}\\ & {\leq |\mathbf{A}_{\omega}^{(1)}|\int_{\omega}\frac{\omega_{\mathrm{D}}^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathrm{D}}^{2}}\int_{\epsilon_{\mathbf{k}}< \omega_{\mathrm{c}}}\frac{k_{\mathrm{F}}^{2}}{v_{\mathrm{F}}^{*}E_{\mathrm{F}}}\frac{|\epsilon_{\mathbf{k}}|}{\omega^{2} + \epsilon_{\mathbf{k}}^{2}} +O(\eta_{\mathrm{e}})}\\ & {\leq |\mathbf{A}_{\omega}^{(1)}|\frac{k_{\mathrm{F}}^{2}}{v_{\mathrm{F}}^{*}E_{\mathrm{F}}}\int_{\omega}\frac{\omega_{\mathrm{D}}^{2}}{(\omega - \omega^{\prime})^{2} + \omega_{\mathrm{D}}^{2}}\ln \left(1 + \frac{\omega_{\mathrm{c}}^{2}}{\omega^{2}}\right) + O(\eta_{\mathrm{e}})}\\ & {= O(\eta_{\mathrm{e}})} \end{array} \quad (D22)\]  

Notice that the integrand vanishes for \(\omega \gg \omega_{\mathrm{D}}\) in the last equation, such that the first term is proportional to \(\omega_{\mathrm{D}} / E_{\mathrm{F}}< \eta_{\mathrm{e}}\)  

To prove Eq. (D15), we taylor expand both \(\mathbf{A}\) and \(\mathbf{B}\) . Since the equation is symmetric with respect to them, we only consider the following leading correction  

\[\begin{array}{r l} & {\left|\int_{\mathbf{k}\omega}(\mathbf{A}_{\omega}^{(1)}\cdot \delta \mathbf{k} / k_{\mathrm{F}})\delta \Pi_{\mathbf{k}\omega}^{\mathrm{s}}B_{k_{\mathrm{F}}\omega}\right|}\\ & {\leq |\mathbf{A}_{0}^{(1)}|\int_{\omega}B_{k_{\mathrm{F}}\omega}\int_{\epsilon_{\mathbf{k}}< \omega_{\mathrm{c}}}\frac{k_{\mathrm{F}}^{2}}{v_{\mathrm{F}}^{*}E_{\mathrm{F}}}\frac{(z^{\mathrm{e}})^{2}|\epsilon_{\mathbf{k}}|\left(\frac{1}{z_{\omega}^{\mathrm{ph}}} - 1\right)\omega^{2}}{(\omega^{2} + \epsilon_{\mathbf{k}}^{2})\left(\frac{\omega}{z_{\omega}^{\mathrm{ph}}}\right)^{2} + \epsilon_{\mathbf{k}}^{2}}}\\ & {\quad +O(\eta_{\mathrm{e}})}\\ & {\leq |\mathbf{A}_{0}^{(1)}|\frac{k_{\mathrm{F}}^{2}}{v_{\mathrm{F}}^{*}E_{\mathrm{F}}}\int_{\omega}\frac{(z^{\mathrm{e}})^{2}B_{k_{\mathrm{F}}\omega}}{(1 + \frac{1}{z_{\omega}^{\mathrm{ph}}})}\ln \left(\frac{\omega^{2} + \omega_{\mathrm{c}}^{2}}{\omega^{2} + (z_{\omega}^{\mathrm{ph}}\omega_{\mathrm{c}})^{2}}\right) + O(\eta_{\mathrm{e}})}\\ & {= O(\eta_{\mathrm{e}})} \end{array} \quad (D23)\]  

Again, notice that the integrand vanishes as \(z_{\omega}^{\mathrm{ph}}\) approaches 1 for \(\omega \gg \omega_{\mathrm{D}}\) . Therefore, the first term is proportional to \(\omega_{\mathrm{D}} / E_{\mathrm{F}}< \eta_{\mathrm{e}}\) .  

In the next step, we extract the low- energy contribution from the electron four- vertex function \(\Gamma^{\mathrm{e}}\) . The first observation is that \(\tilde{\Gamma}^{\mathrm{*}}\) in Eq. (C23) inherits the Coulomb singularity in \(\tilde{\Gamma}\) . This can be proved by contradiction if we rewrite  

\[\tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}} + \int_{\mathbf{k}^{\prime \prime}\omega^{\prime \prime}}\phi_{\mathbf{k}\omega ;\mathbf{k}^{\prime \prime}\omega^{\prime \prime}}\tilde{\Gamma}_{\mathbf{k}^{\prime \prime}\omega^{\prime \prime};\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}} = \tilde{\Gamma}_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}} \quad (D24)\]  

If \(\tilde{\Gamma}^{\mathrm{e}}\) is a regular function, the l.h.s is also regular, which contradicts the Coulomb singularity in the r.h.s. Therefore, following Eq. (C24), we separate \(\Gamma^{\mathrm{e}}\) into three distinct contributions as follows:  

\[\Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}} = \Gamma_{0}^{\mathrm{e}} + W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{\mathrm{s}} + \delta \Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}. \quad (D25)\]  

Here, \(\Gamma_{0}^{\mathrm{e}}\) represents the Fermi surface- averaged electron vertex function, formally given by  

\[\Gamma_{0}^{\mathrm{e}}\equiv \langle \Gamma_{\mathbf{k}\omega ;\mathbf{k}^{\prime}\omega^{\prime}}^{\mathrm{e}}\rangle_{\left|\mathbf{k}\omega \right| = \left|\mathbf{k}^{\prime}\omega^{\prime}\right| = (k_{\mathrm{F}},\pi T)}. \quad (D26)\]  

This term scales as \(\propto \frac{1}{1 + g_{0}\ln(\omega_{\mathrm{p}} / T)}\) at temperatures much lower than \(\omega_{\mathrm{p}}\) as given by Eq. (C24). The Coulomb singularity \(W^{s}\) follows the same parametrization in Eq. (C8). The remaining part of the full electron vertex function is denoted as \(\delta \Gamma\) . It should be regular up to the scale the momentum scale \(k_{\mathrm{F}}\) and the energy scale \(v_{\mathrm{F}}^{*}k_{\mathrm{F}}\) .  

The problem could be simplified significantly if the plasmon mode is gapped as in 3D electron system with moderate \(r_{\mathrm{s}}\) or the interaction between electrons are short- range. In what follows, we demonstrate that the singular component \(W_{\mathbf{k} - \mathbf{k}^{\prime},\omega -\omega^{\prime}}^{\mathrm{s}}\) contributes terms that scale as \(O(\eta_{\mathrm{p}}^{2},\eta_{\mathrm{e}})\) , where \(\eta_{\mathrm{p}} = \omega_{\mathrm{c}} / \omega_{\mathrm{p}}\) . This scaling behavior implies that both the \(W^{s}\delta \Pi \Lambda\) and \(W^{s}\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda\) terms make negligible contributions to the overall result. It is important to note, however, that this does not diminish the relevance of the plasmon mode itself—rather, its contribution is already effectively captured within \(\Gamma_{0}^{\mathrm{e}}\) .  

To estimate the contributions from \(W^{s}\delta \Pi \Lambda\) and \(W^{s}\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda\) , we first consider their low frequency components. Considering a spherical Fermi surface, the momentum integration in \(W^{s}\delta \Pi \Lambda\) takes the form:  

\[\int k^{\prime 2}dk^{\prime}\ln (|k^{\prime} - k_{\mathrm{F}}|)\delta \Pi_{k^{\prime}\omega^{\prime}}\Lambda_{k^{\prime}\omega^{\prime}} = \frac{C}{|\omega^{\prime}|}\Theta (\omega_{\mathrm{D}} - |\omega^{\prime}|) + \mathrm{reg}, \quad (D27)\]  

where \(C\) represents a constant factor. This result arises from two key observations. First, \(\Lambda_{\mathbf{k}^{\prime},\omega^{\prime}}\) , as derived in Eq. (C20), remains smooth near \(\omega = 0\) and \(|\mathbf{k}^{\prime}| = k_{\mathrm{F}}^{\prime}\) . Second, \(\delta \Pi_{k^{\prime}\omega^{\prime}}\) decays at high frequencies \((\omega^{\prime}\gg \omega_{\mathrm{D}}^{\prime})\) as \(z_{\mathrm{ph}}^{2}(\omega^{\prime})\) approaches unity, leading to the \(\Theta (\omega_{\mathrm{D}}^{\prime} - |\omega^{\prime}|)\) constraint. For frequencies below \(\omega_{\mathrm{D}}^{\prime}\) , \(\delta \Pi_{k^{\prime}\omega^{\prime}}\) consists of two terms scaling as \(1 / (\omega^{\prime 2} + (v_{\mathrm{F}}^{*}(k^{\prime} - k_{\mathrm{F}})^{2})\) , leading to the singular \(1 / |\omega^{\prime}|\) behavior.  

We denote the low frequency components \((\omega \lesssim \omega_{\mathrm{D}})\) by \(\mathrm{L}\) and the high frequency components \((\omega_{\mathrm{D}}\ll \omega \lesssim \omega_{\mathrm{c}})\) by



H. Then we have  

\[\begin{array}{r l r} & {} & {[W_{\mathrm{s}}\delta \Pi \Lambda ]_{L}\sim \sum_{\omega^{\prime}}\frac{\omega^{\prime 2}}{\omega^{\prime 2} + \omega_{\mathrm{p}}^{2}}\frac{1}{|\omega^{\prime}|}\Theta (\omega_{\mathrm{D}} - |\omega^{\prime}|)}\\ & {} & {\propto \frac{\omega_{\mathrm{D}}^{2}}{\omega_{\mathrm{p}}^{2}} = O(\eta_{\mathrm{p}}^{2}\eta_{c}^{2}).} \end{array} \quad (D28)\]  

Similarly, the smallness of \(W_{\mathrm{s}}\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda\) at low frequencies can be demonstrated through  

\[\begin{array}{r l r}{[W_{\mathrm{s}}\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda ]_{L}\sim} & {\sum_{|\omega^{\prime}|,|\omega^{\prime \prime}|< \omega_{\mathrm{c}}}\frac{\omega^{\prime} - \omega^{\prime\prime}|< \omega_{\mathrm{D}}}{\omega^{\prime 2} + \omega_{\mathrm{p}}^{2}}\frac{1}{|\omega^{\prime}|}\frac{1}{|\omega^{\prime\prime}|}}\\ & {\sim} & {\sum_{|\omega^{\prime}|< \omega_{\mathrm{c}}}\frac{\omega_{\mathrm{D}}}{\omega^{\prime 2} + \omega_{\mathrm{p}}^{2}}}\\ & {\propto} & {\frac{\omega_{\mathrm{D}}}{\omega_{\mathrm{p}}} = O(\eta_{\mathrm{e}}\eta_{\mathrm{p}}),} \end{array} \quad (D29)\]  

Here, the \(1 / |\omega^{\prime}|\) and \(1 / |\omega^{\prime \prime}|\) terms arise from the momentum integration of \(W_{\mathrm{s}}\Pi^{\mathrm{e}}\) and \(\Pi \Lambda\) , whereas the frequency summation constraint is due to the vanishing of \(W^{\mathrm{ph}}\) at \(|\omega^{\prime} - \omega^{\prime \prime}|\gg \omega_{\mathrm{D}}\) .  

In addition, we must estimate the contribution at frequencies \(\omega \sim \omega_{\mathrm{c}}\) , since \(\Lambda\) appears in the self- consistent equations for frequencies below \(\omega_{\mathrm{c}}\) . Similar to the low frequency components, we have  

\[\begin{array}{r l r}{[W_{\mathrm{s}}\delta \Pi \Lambda ]_{\mathrm{H}}\sim \sum_{\omega^{\prime}}\frac{(\omega^{\prime} - \omega_{\mathrm{c}})^{2}}{(\omega^{\prime} - \omega_{\mathrm{c}})^{2} + \omega_{\mathrm{p}}^{2}}\frac{1}{|\omega^{\prime}|}\Theta (\omega_{\mathrm{D}} - |\omega^{\prime}|)}\\ & {} & {\propto \frac{\omega_{\mathrm{c}}^{2}}{\omega_{\mathrm{p}}^{2}} = O(\eta_{\mathrm{p}}^{2}),} \end{array} \quad (D30)\]  

and  

\[\begin{array}{r l r}{[W_{\mathrm{s}}\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda ]_{H}\sim} & {\sum_{|\omega^{\prime}|,|\omega^{\prime \prime}|< \omega_{\mathrm{c}}}\frac{(\omega^{\prime} - \omega_{\mathrm{c}})^{2}}{(\omega^{\prime} - \omega_{\mathrm{c}})^{2} + \omega_{\mathrm{p}}^{2}}\frac{1}{|\omega^{\prime}|}\frac{1}{|\omega^{\prime\prime}|}}\\ & {} & {\propto \frac{\omega_{\mathrm{c}}^{2}}{\omega_{\mathrm{p}}^{2}} = O(\eta_{\mathrm{p}}^{2}).} \end{array} \quad (D31)\]  

These contributions are also small; however, they are controlled by \(\eta_{\mathrm{p}}\) alone, contrary to the low frequency contributions that are controlled by \(\eta_{\mathrm{p}}\eta_{\mathrm{e}}\) . Although these high- frequency contributions do not affect the phonon physics, they do affect the renormalization of the electron- electron interaction. If the condition \(\eta_{\mathrm{p}}\ll 1\) is not met, these terms will contribute a correction to the pseudopotential proportional to \(\eta_{\mathrm{p}}^{2}\) .  

After applying this approximation we can simplify Eq. (D10) to  

\[\begin{array}{r l r} & {\Lambda = \Lambda^{\mathrm{e}} + (\Gamma_{\mathrm{e}}^{\mathrm{e}} + \delta \Gamma)\delta \Pi \Lambda}\\ & {} & {+[1 + (\Gamma_{\mathrm{e}}^{\mathrm{e}} + \delta \Gamma)\Pi^{\mathrm{e}}]W^{\mathrm{ph}}\Pi \Lambda +O(\eta_{\mathrm{p}}^{2},\eta_{\mathrm{e}}).} \end{array} \quad (D32)\]  

Now using Eqs. (D14) and (D15), we have  

\[(\Gamma_{\mathrm{e}}^{\mathrm{e}} + \delta \Gamma)\delta \Pi \Lambda = \Gamma_{\mathrm{e}}^{\mathrm{e}}\delta \Pi^{\mathrm{e}}\bar{\Lambda} +O(\eta_{\mathrm{e}}), \quad (D33)\]  

\[W^{\mathrm{ph}}\Pi \Lambda = \bar{W}^{\mathrm{ph}}\Pi^{\mathrm{e}}\bar{\Lambda} +O(\eta_{\mathrm{e}}), \quad (D34)\]  

and  

\[(\Gamma_{\mathrm{e}}^{\mathrm{e}} + \delta \Gamma)\Pi^{\mathrm{e}}W^{\mathrm{ph}}\Pi \Lambda = \Gamma_{\mathrm{e}}^{\mathrm{e}}\Pi^{\mathrm{e},\mathrm{s}}\bar{W}^{\mathrm{ph}}\Pi^{\mathrm{e}}\bar{\Lambda} +O(\eta_{\mathrm{e}}), \quad (D35)\]  

where \(\bar{W}_{\omega ,\omega^{\prime}}^{\mathrm{ph}} = W_{\mathbf{k}_{\mathrm{F}}\omega ;\mathbf{k}_{\mathrm{F}}\omega^{\prime}}^{\mathrm{ph}}\) , and \(\bar{\Lambda}^{\mathrm{e}}\equiv \Lambda_{\omega}^{\mathrm{e}}\equiv \Lambda_{\mathbf{k}_{\mathrm{F}}\omega}^{\mathrm{e}}\) . And the equation becomes  

\[\bar{\Lambda} = \bar{\Lambda}^{\mathrm{e}} + \Gamma_{\mathrm{e}}^{\mathrm{e}}\delta \Pi^{\mathrm{e}}\bar{\Lambda} +(1 + \Gamma_{\mathrm{e}}^{\mathrm{e}}\Pi^{\mathrm{e},\mathrm{s}})\bar{W}^{\mathrm{ph}}\Pi^{\mathrm{e}}\bar{\Lambda} +O(\eta_{\mathrm{e}},\eta_{\mathrm{p}}^{2}), \quad (D36)\]  

where \(\bar{\Lambda}_{\omega} = \Lambda_{k_{\mathrm{F}},\omega}\) . Notice that in this equation the momentum dependences only appear in \(\Pi^{\mathrm{s}}\) , \(\Pi^{\mathrm{e},\mathrm{s}}\) and \(\delta \Pi^{\mathrm{s}}\) , and can be integrated out.  

Further substitute \(\Gamma_{\mathrm{e}}^{\mathrm{e}}\) with  

\[U = \Gamma_{\mathrm{e}}^{\mathrm{e}} - \Gamma_{\mathrm{e}}^{\mathrm{e}}\Pi^{\mathrm{e},\mathrm{s}}U, \quad (D37)\]  

where by subtracting the Cooper logarithm from \(\Gamma_{\mathrm{e}}^{\mathrm{e}}\) , \(U\) is now temperature independent and serves as the TMA pseudopotential in our equation below. And the Eq. (D10) is further simplified as  

\[\bar{\Lambda}_{\omega} = \eta_{\omega} + \sum_{\omega^{\prime}}(U + \bar{W}_{\omega^{\prime}}^{\mathrm{ph}}\bar{\Lambda}_{\omega^{\prime}}^{\mathrm{e}})\bar{\Pi}_{\omega^{\prime}}^{\mathrm{e}}\bar{\Lambda}_{\omega^{\prime}} + O(\eta_{\mathrm{e}},\eta_{\mathrm{p}}^{2}), \quad (D38)\]  

where  

\[\eta_{\omega} = \bar{\Lambda}_{\omega}^{\mathrm{e}} - U\int_{\omega^{\prime}}\Pi_{\omega^{\prime}}^{\mathrm{e},\mathrm{s}}\Lambda_{\omega^{\prime}}^{\mathrm{e}} \quad (D39)\]  

and  

\[\bar{\Pi}_{\omega}^{\mathrm{s}} = \frac{2(z^{\mathrm{e}})^{2}z_{\omega}^{\mathrm{ph}}\tan^{-1}\left(\frac{z_{\omega}^{\mathrm{ph}}\omega_{\mathrm{c}}}{\left|\omega\right|}\right)}{v_{\mathrm{F}}^{*}\left|\omega\right|} \quad (D40)\]  

The source term \(\eta_{\omega}\) is temperature independent in the low frequency part, and the form of this term has no effects on the resulting \(T_{\mathrm{c}}\) , thus we can simply set this quantity to unity in calculations. This results in correct \(T_{\mathrm{c}}\) , but the obtained \(\Lambda_{0}\) will differ by a factor from the exact one.  

While the \(\bar{\Pi}_{\omega}^{\mathrm{s}}\) defined in Eq. (D40) does not contain an explicit cut- off in frequency domain, the additional inverse tangent factor guarantees the decay of this function above \(\omega_{\mathrm{c}}\) . In numerical calculations, an alternative form of \(\bar{\Pi}_{\omega}^{\mathrm{s}}\) with hard cut- off would be more convenient:  

\[\bar{\Pi}_{\omega}^{\mathrm{s}} = \frac{2(z^{\mathrm{e}})^{2}z_{\omega}^{\mathrm{ph}}}{v_{\mathrm{F}}^{*}\left|\omega\right|}\Theta (\omega_{\mathrm{c}} - \left|\omega\right|). \quad (D41)\]  

There should be no additional difficulties to show all the derivation above still holds for this choice of form.



## Appendix E: First-Principle Calculations of the Vertex Functions  

Now we explain how to compute the relevant vertex functions in the UEG model with the help of VDiagMC approach. These include the Coulomb pseudopotential derived in the previous section by sampling the twoquasiparticle scattering amplitude averaged on Fermi surface [see Eq. (D26)], and the 3- vertex appearing in the phonon- induced interaction \(W^{\mathrm{ph}}\) . Here we adopt the same convention for three dimension with angular momentum quantum number \(\ell = 0\) , which corresponds to the s- wave case.  

## 1 Spin and Angular Momentum Conventions  

The UEG model pertains full translational and rotational symmetries, and the superconducting properties depends on the symmetry channel. In this work, we focused on the s- wave spin singlet superconductivity, although the conventions presented below were generic. The generic discussion of angular momentum decomposition of the PCF equation could be found in Appendix A of Ref. [25].  

To illustrate the spin convention, we use Greek letter \(\alpha ,\beta ,\gamma ,\delta\) to represent the spin degree of freedom and abbreviate the space coordinates of particles with numbers. Then, the response function \(\Lambda_{\alpha \beta}(12)\) , like the gapfunction of superconductivity, has the following property:  

\[\Lambda_{\alpha \beta}(12) = -\Lambda_{\beta \alpha}(21). \quad (E1)\]  

It is more convenient to decompose the spin configuration of the response function into the singlet and triplet components,  

\[\begin{array}{l}\Lambda_{\mathrm{s}}(12) = \frac{1}{2} (\Lambda_{\uparrow \downarrow}(12) - \Lambda_{\downarrow \uparrow}(12))\\ \displaystyle \Lambda_{\mathrm{t}}(12) = \frac{1}{2} (\Lambda_{\uparrow \downarrow}(12) + \Lambda_{\downarrow \uparrow}(12)) \end{array} \quad (E2)\]  

such that \(\Lambda_{\mathrm{s}}(12) = \Lambda_{\mathrm{s}}(21)\) , \(\Lambda_{\mathrm{t}}(12) = - \Lambda_{\mathrm{t}}(21)\) . And similarly we have \(F_{\mathrm{s} / \mathrm{t}}(12) = \int_{34}G(13)\Lambda_{\mathrm{s} / \mathrm{t}}(34)G(42)\) .  

For 4- vertices, the direct and exchange components contribute equally in Cooper channel, thus we needed to consider only the direct part. For direct part we had  

\[\Gamma_{\alpha \beta \gamma \delta}^{\mathrm{d}}(12;34)\equiv \Gamma_{12;34}^{+}\delta_{\alpha \beta}\delta_{\gamma \delta} + \Gamma_{12;34}^{-}\bar{\sigma}_{\alpha \beta}\cdot \bar{\sigma}_{\gamma \delta}. \quad (E3)\]  

Then the equation  

\[\Lambda_{\alpha \gamma} = \eta_{\alpha \gamma} + \Gamma_{\alpha \beta \gamma \delta}^{\mathrm{d}}F_{\alpha \gamma} \quad (E4)\]  

could be decomposed as  

\[\begin{array}{l}\Lambda_{\mathrm{s}} = \eta_{\mathrm{s}} + (\Gamma^{\mathrm{s}} - 3\Gamma^{\mathrm{a}})F_{\mathrm{s}},\\ \Lambda_{\mathrm{t}} = \eta_{\mathrm{t}} + (\Gamma^{\mathrm{s}} + \Gamma^{\mathrm{a}})F_{\mathrm{t}}. \end{array} \quad (E5)\]  

In diagMC implementation, it is more convenient to work with the following convention for 4- vertices:  

\[\begin{array}{r}\Gamma_{\mathrm{uu}}(12;34) = \Gamma_{\mathrm{12;34}}^{+} + \Gamma_{\mathrm{12;34}}^{-},\\ \Gamma_{\mathrm{ud}}(12;34) = \Gamma_{\mathrm{12;34}}^{+} - \Gamma_{\mathrm{12;34}}^{-}. \end{array} \quad (E6)\]  

Thus  

\[\begin{array}{r}\Gamma^{\mathrm{s}} = \Gamma^{+} - 3\Gamma^{-} = -\Gamma_{\mathrm{uu}} + 2\Gamma_{\mathrm{ud}},\\ \Gamma^{\mathrm{t}} = \Gamma^{+} + \Gamma^{-} = \Gamma_{\mathrm{uu}}. \end{array} \quad (E7)\]  

Since the Coulomb pseudopotential is defined for s- wave superconductivity, only the singlet case was considered in this work. However, there is no restriction to extend the definition to higher angular momentum cases, where even \(\ell\) corresponds to spin singlet state and odd \(\ell\) corresponds to triplet.  

In addition, we defined dimensionless versions of \(\Gamma_{\mathrm{0}}^{\mathrm{e}}\) and \(U\) as \(\gamma_{0} = z_{\mathrm{e}}^{2}N_{\mathrm{F}}^{\ast}\Gamma_{\mathrm{0}}^{\mathrm{e}}\) and \(u = UN_{\mathrm{F}}^{\ast}\) , with \(N_{\mathrm{F}} = \frac{m^{*}k_{\mathrm{F}}}{2\pi^{2}}\) . Note that the spin factor is omitted as the spin degree of freedom is accounted as described above. We evaluated the direct and exchange components on equal footing, thus the \(\Gamma_{0}\) is obtained by taking half the value.  

## 2 First-principle approach to the pseudopotential  

As mentioned in Sec.[main], we computed the selfenergy and four- point vertex function for the renormalized UEG theory with VDiagMC. In this section we explained the details of these calculations.  

## a Self-energy expansion  

The self- energy calculation followed the approach explained in Ref. [82]. Here we only briefly illustrated the procedure.  

After performing the \(\xi\) expansion mentioned in Sec.[main] in the main text, the self- energy was expanded as a series  

\[\Sigma (\xi) = \sum_{n}\xi^{n}\Sigma^{(n)}, \quad (E8)\]  

where each term \(\Sigma^{(n)}\) represents a group of diagrams that could be evaluated stochastically as explained in Ref.[82]. The desired quantities, quasiparticle weight and the effective mass, was then given by the equation  

\[z^{\mathrm{e}} = \left(1 - \frac{\partial\mathrm{Im}\Sigma(k_{\mathrm{F}},i\omega)}{\partial(i\omega)}\bigg|_{\omega = 0}\right)^{-1}, \quad (E9)\]  

and  

\[\frac{m_{\mathrm{e}}^{*}}{m} = \frac{1}{z^{\mathrm{e}}}\cdot \left(1 + \frac{m}{k_{\mathrm{F}}}\frac{\partial\mathrm{Re}\Sigma(k,0)}{\partial k}\bigg|_{\substack{k = k_{\mathrm{F}}}}\right)^{-1}. \quad (E10)\]



Plugging in Eq.(E8) resulted in a series expansion of these quantities with respect to \(\xi\) :  

\[z^{\mathrm{e}} = 1 + \sum_{n = 1}^{\infty}\delta z^{(n)}\xi^{n}, \quad (E11)\]  

and  

\[\bar{m} = \frac{m_{\mathrm{e}}^{*}}{m} = 1 + \sum_{n = 1}^{\infty}\delta m^{(n)}\xi^{n}. \quad (E12)\]  

## b Four-point vertex expansion  

The same diagrammatic expansion as the self- energy was performed for the four- point vertex, and this resulted in a series expansion of \(\Gamma^{\mathrm{e}}\) . To obtain the dimensionless quasiparticle scattering amplitude \(\gamma_{T}\) , we needed to multiply \(z^{\mathrm{e}}\) and \(\frac{m_{\mathrm{e}}^{*}}{m}\) , and also \(N_{\mathrm{F}}\) onto it. The effective mass part was straightforward. We simply multiply the series of \(\Gamma^{\mathrm{e}}\) and \(\frac{m_{\mathrm{e}}^{*}}{m}\) term- by- term and collect the results as a series of \(\xi\) . The quasiparticle residue part was less trivial. To optimize the convergence, we multiplied the \([z^{\mathrm{e}}(\xi)]^{2}\) not on the final series of \(\Gamma^{\mathrm{e}}\) , but on the interaction \(v_{\mathrm{R}}\) within the expansion. The diagrams thus generated was again re- grouped as a series of \(\xi\) . By doing so, the higher order counterterms generated by the series expansion of \(z^{\mathrm{e}}\) canceled the contributions from the vertex correction and electron's self- energy, yielding a better convergence. The relation between \(z^{\mathrm{e}}\) and 3- vertex correction could be found in Sec. E3.  

## c Frequency cut-off shift  

While the converged result of \(\mu\) was determined solely by the chosen frequency cut- off \(\omega_{c}\) , the finite- order expansion was less- trivial. In a finite- order expansion as given in previous sections, the Green's functions in the Cooper ladder diagrams are only resummed up to a finite- order, resulting in a finite- order effective mass appearing in it. This finite- order effective mass differs from the converged one, thus affected the logarithmic divergent terms generated from the ladder diagram. Specifically, when the cutoff was introduced from the momentum space, the momentum cut- off was determined by \(\Delta k = \omega_{c} / v_{\mathrm{F}}^{*} \propto \bar{m} \omega_{c}\) . The cut- off \(\omega_{c}\) should be fixed for all orders, but for finite order diagrams, the effective mass appears only as a finite order correction, resulting in a different \(\Delta k\) for different order. Thus, in order to cancel out this effect, an additional \(\bar{m}^{(n)}\) needed to appear in the logarithmic divergence factor, resulting in \(\ln (\frac{\bar{m}^{(n)} \omega_{c}}{T})\) instead of \(\ln (\frac{\omega_{c}}{T})\) . This could in turn be regarded as an effective cut- off shift to  

\[\omega_{c}^{(n)} = \omega_{c}(1 + \sum_{i = 1}^{n}\delta m^{(i)}). \quad (E13)\]  

The n- th order result \(\mu^{(n)}(\omega_{c}^{(n)})\) could be obtained by subtracting the Cooper instability logarithm from the \(\gamma\) series as Eq.(30) showed, with proper frequency cut- off inserted:  

\[\begin{array}{l}\mu^{(1)} = \gamma_{T}^{(1)},\\ \mu^{(2)} = \gamma_{T}^{(2)} - \gamma_{T}^{(1)}\ln (\omega_{c}^{(n)} / T)\gamma_{T}^{(1)},\\ \qquad \dots \end{array} \quad (E14)\]  

The series of \(\mu\) could then be shifted back to the desired cutoff by  

\[\mu^{(n)}(\omega_{c}) = \frac{\mu^{(n)}(\omega_{c}^{(n)})}{1 + \mu^{(n)}(\omega_{c}^{(n)})\ln(\omega_{c}^{(n)} / \omega_{c})}, \quad (E15)\]  

and sum up to the highest computed order. This leads to an estimation of \(\mu\) to this order with cutoff \(\omega_{c}\) .  

By doing so, the contribution of effective mass to the logarithmic divergent terms could be canceled out order by order. To see this, consider third order (contribution does not appear until the third order) expansion of \(\mu\) .  

For the third order, we have  

\[\begin{array}{r}\mu^{(3)} = \gamma^{(3)} + \delta m^{(1)}\gamma^{(2)} + \delta m^{(2)}\gamma^{(1)}\\ -2\gamma^{(1)}L\gamma^{(2)} - 2\gamma^{(1)}L\gamma^{(1)}\delta m^{(1)}\\ +\gamma^{(1)}L\gamma^{(1)}L\gamma^{(1)}, \end{array} \quad (E16)\]  

where \(L = \ln (\omega_{c} / T)\) . The logarithmic divergent contribution of third order particle- particle reducible diagram with one particle propagator dressed by first order self- energy, and of \(\delta m^{(1)}\gamma^{(2)}\) , are canceled by \(- 2\gamma^{(1)}L\gamma^{(1)}\delta m^{(1)}\) term.  

## d Mathematical Status of the Resummation Protocol  

The mathematical status of the implemented resummation protocol relies on the analyticity of \(\gamma_{T}(\xi)\) . Our only assumption—not fully controlled but reasonable at the level of self- consistency—is the analyticity of \(\gamma_{T}(\xi)\) as a function of complex \(\xi\) within a certain domain containing points \(\xi = 0\) and \(\xi = 1\) . This implies that the r.h.s. of Eq. (28) is the Taylor expansion (convergent at small enough \(|\xi |\) ) of \(\gamma_{T}(\xi)\) at the point \(\xi = 0\) that uniquely defines—by analytic continuation—the desired value of \(\gamma_{T}(\xi = 1)\) . The rest is a mathematically rigorous method of resummation of a Taylor series of an analytic function by the conformal map technique outlined in the following.  

Let \(f(\xi)\) be a certain analytic function represented by the (Taylor) expansion in powers of the complex argument \(\xi\) . In the most general case, the conformal map analytically transforms both the function \(f\) and its argument \(\xi\) so that we deal with a new analytic function, \(g\) , of a new argument, \(w\) :  

\[g(w) = Q(f(\xi (w)),w). \quad (E17)\]



Here, the old argument \(\xi\) is replaced with a new argument \(w\) by introducing an analytic function \(\xi \equiv \xi (w)\) , such that \(\xi (w = 0) = 0\) , \(\xi (w = 1) = 1\) ; and the old function \(f(\xi)\) is replaced with the new function \(g(w)\) with the help of the function \(Q(f,w)\) , the form of which can be quite arbitrary provided the resulting function \(g(w)\) is analytic at any \(|w| \leq 1\) . The resummation procedure amounts to finding the value of \(g(w = 1)\) by summing up its Taylor expansion in powers of \(w\) ; the coefficients of the series being related to the coefficients of the original series for \(f(\xi)\) by expanding the r.h.s. of Eq. (E17) in powers of \(w\) . The estimated value of \(g(w = 1)\) then allows one to find the desired value of \(f(\xi = 1)\) from Eq. (E17).  

The most commonly used particular form of conformal map resummation does not involve introducing a new function. Less common but most relevant for our work is yet another particular case in which one introduces a new function while working with the old variable \(\xi\) :  

\[g(\xi) = Q(f(\xi),\xi). \quad (E18)\]  

This type of conformal map is natural when the function \(g(\xi)\) , rather than the series- generating function \(f(\xi)\) , is of our main interest, so that there is no need to restore \(f\) from \(g\) . Our case is precisely like that: The series- generating function \(\gamma_{T}(\xi)\) is conformally mapped onto the function of our interest, \(\mu_{\omega_{\mathrm{c}}}(\xi)\) , and the estimated value of \(\mu_{\omega_{\mathrm{c}}}(\xi = 1)\) is then used to extract \(\mu_{E_{\mathrm{F}}}\) .  

In the absence of a proof of the analyticity of \(\gamma_{T}(\xi)\) as a function of \(\xi\) , we formulate an a posteriori argument in favor of the consistency of our resummation protocol. The argument is two- fold: (i) the fact of the convergence of the series Eq. (29) at \(\xi = 1\) within a certain range of the values of parameter \(\omega_{\mathrm{c}}\) , defining the particular form of the coefficients of the series; and (ii) the independence of the extracted result for \(\mu_{E_{\mathrm{F}}}\) from the particular choice of \(\omega_{\mathrm{c}}\) .  

## e Results  

An example of temperature dependence of series expansion of \(\gamma_{T}\) and \(\mu\) , computed at \(r_{\mathrm{s}} = 1.0\) with \(\lambda_{\mathrm{R}} = 3.5\) , were presented in Fig.7. The converged results for \(r_{\mathrm{s}} = 1\) to 6 were shown in Fig. 14.  

## 3 First-principle approach to the 3-Vertex  

In this section, we show the validity of the ansatz Eq. (D2) in the context of UEG by comparing it with the VDMC results. Two additional series expansions need to be obtained in order to give the desired quantity \(W\Gamma_{3}^{\mathrm{e}}\) : the proper 3- vertex \(\Gamma_{3}^{\mathrm{e}}\) and the polarization \(P\) (we use \(P\) to represent polarization in this section to distinguish it from the quasiparticle pair- field propagator). In addition, a series of exchange- correlation kernel \(f_{\mathrm{xc}}\) with its convergent value are also needed for better convergence  

![](images/33_0.jpg)

<center>FIG. 14. Sixth order series of the pseudopotential \(\mu (\omega_{\mathrm{c}} = 0.1E_{\mathrm{F}})\) for \(r_{\mathrm{s}} = 1\) to 6. For each \(r_{\mathrm{s}}\) , results from two \(\lambda\) were presented. The light green labels the range of estimated convergent result from the data. </center>  

of the series. All these functions could be obtained with VDMC sampling in a similar way as described in the last subsection, with the diagrammatic expansion altered to the corresponding ones.  

The post- processing of these results need to be done cautiously such that terms with bad convergence cancels each other order by order. Specifically, the polarization and proper 3- vertex is characterized by the following ansatz for moderate \(r_{\mathrm{s}}\) :  

\[P = \frac{P}{1 - f_{\mathrm{xc}}P^{(0)}} +\mathrm{correction}, \quad (E19)\]  

and  

\[z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}} = \frac{1}{1 - f_{\mathrm{xc}}P^{(0)}} +\mathrm{correction}, \quad (E20)\]  

where \(P^{(0)}\) is the bare polarization. At around \(r_{\mathrm{s}} = 5\) , the denominator began to vanish at small \(\mathbf{q}\) , resulting in a divergent series for both quantities. However, if handled correctly, the divergence cancels each other.  

First, we compute the series of \(z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}}\) and \(P\) , which are not converging around \(r_{\mathrm{s}} \approx 5\) . Then, we compute two quantities, \(z^{\mathrm{e}}\Gamma_{3}^{\mathrm{e}} / P\) and \(WP\) . By carefully cancel the divergent terms order by order, the series of these two quantities could be made convergent. In the end, we multiply them to obtain the final result \(z_{\mathrm{e}}\Gamma^{3e}v_{\mathbf{q}}\) . Below we discuss step- by- step how this could be done.  

Suppose we have series expansions  

\[z^{\mathrm{e}}(\xi)\Gamma_{3}^{\mathrm{e}}(\xi) = 1 + \xi \delta \Gamma_{3}^{(1)} + \xi^{2}\delta \Gamma_{3}^{(2)} + \ldots , \quad (E21)\]



and  

\[P(\xi) = P^{(0)} + \xi \delta P^{(1)} + \xi^{2}\delta P^{(2)} + \ldots , \quad (E22)\]  

and we write \(\Gamma_{3}^{(n)} = \sum_{i = 0}^{n}\xi^{i}\delta \Gamma_{3}^{(i)}\) with \(\Gamma_{3}^{(0)} = \delta \Gamma_{3}^{(0)} = 1\) and \(P^{(n)} = \sum_{i = 0}^{n}\xi^{i}\delta P^{(i)}\) with \(P^{(0)} = \delta P^{(0)}\) . Then we have the expansion series of \(\Gamma_{3} / P\) given by  

\[\delta (\Gamma_{3} / P)^{(i)} = \frac{\delta\Gamma_{3}^{(i)}P^{(i - 1)} - \Gamma_{3}^{(i - 1)}\delta P^{(i)}}{P^{(i)}P^{(i - 1)}}, \quad (E23)\]  

with \((\Gamma_{3} / P)^{(0)} = 1 / P^{(0)}\) . The diverging part in the numerator cancels, resulting in a convergent series of \(\Gamma_{3} / P\) .  

The situation is different for the \(WP\) term. For \(WP\) we have  

\[WP = -\frac{P}{P - v_{\mathbf{q}}^{-1}}, \quad (E24)\]  

which expands with respect to the series of \(P\) as  

\[\delta (WP)^{(i)} = \frac{v_{\mathbf{q}}^{-1}\delta P^{(i)}}{(P^{(i)} - v_{\mathbf{q}}^{-1})(P^{(i - 1)} - v_{\mathbf{q}}^{-1})}, \quad (E25)\]  

with \((WP)^{(0)} = -\frac{P^{(0)}}{P^{(0)} - v_{\mathbf{q}}^{-1}}\) . It could be seen that a bad convergence of \(P\) leads to a bad convergence of \(WP\) unless \(\mathbf{q} = 0\) . Thus we need to first obtain a convergent series of \(P\) . To do this, we first compute \(P(1 - f_{\mathrm{xc}}P^{(0)})\) order by order. Suppose we have the series expansion of \(f_{\mathrm{xc}}\) with the same expansion parameters as \(P\) ,  

\[f_{\mathrm{xc}} = \xi f^{(1)} + \xi^{2}\delta f^{(2)} + \xi^{3}\delta f^{(3)} + \ldots , \quad (E26)\]  

and \(f^{(n)} = \sum_{i = 1}^{n}\delta f^{(i)}\) with \(f^{(1)} = \delta f^{(1)}\) , \(f^{(0)} = 0\) . Then the series expansion of \(P(1 - f_{\mathrm{xc}}P^{(0)})\) is given by  

\[\begin{array}{r}\delta \left[P(1 - f_{\mathrm{xc}}P^{(0)})\right]^{(i)} = \delta P^{(i)}(1 - f^{(i - 1)}P^{(0)})\\ -P^{(i - 1)}\delta f^{(i)}P^{(0)} - \delta P^{(i)}\delta f^{(i)}P^{(0)}. \end{array} \quad (E27)\]  

The convergent series of \(P\) is then obtained by divide \((1 - f_{\mathrm{xc}}P^{(0)})\) from the convergent series \(P(1 - f_{\mathrm{xc}}P^{(0)})\) with converged result of \(f_{\mathrm{xc}}\) . This converged result of \(f_{\mathrm{xc}}\) could be obtained from other expansion series with different parameters. The convergent series of \(WP\) could then be computed and the final result could be obtained by multiplying the above results together. Results of this convergent series were shown in Fig.8.  

![](images/34_0.jpg)

<center>FIG. 15. Pressure dependence of the Aluminum lattice constant. The red squares represent experimental data from Ref. [100], and the solid blue line denotes the quadratic fit used in this work to determine the structural parameters for finite-pressure calculations. </center>  

## Appendix F: Equation of State for Aluminum  

To determine the lattice parameter of FCC- Al as a function of pressure, we performed a fit to the experimental data from Ref. [100] using a second- order polynomial. The resulting equation of state (EOS) allows us to interpolate the lattice constants used in our DFT calculations at arbitrary pressures. FIG. 15 displays the experimental data alongside our fitted curve, showing excellent agreement over the pressure range of interest.


