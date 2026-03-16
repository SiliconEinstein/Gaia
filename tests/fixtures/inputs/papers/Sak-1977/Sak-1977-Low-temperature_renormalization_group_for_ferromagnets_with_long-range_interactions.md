
# Low-temperature renormalization group for ferromagnets with long-range interactions \( ^{*} \) 

J. Sak

Serin Physics Laboratory, Rutgers University, New Brunswick, New Jersey 08903
(Received 2 December 1976)

Ferromagnets with the number of spin components n > 2 and with power-law interactions  \( r^{-d-\sigma} \)  are studied in dimensions  \( d = 2 + \epsilon \)  for small  \( \epsilon \) . The following theorem is proved: Let  \( \eta_{SR} \)  be the value of the critical exponent  \( \eta \)  for short-range force (e.g., nearest-neighbor exchange). Then in the presence of the long-range power-law interaction the critical behavior is the same as for short-range interactions provided that the inequality  \( 2 - \sigma < \eta_{SR} \)  is satisfied. In this case the critical exponents depend on d and n but not on  \( \sigma \) . In the opposite case, the value of  \( \eta \)  is  \( \eta_{LR} = 2 - \sigma \)  and the critical exponent  \( \nu \)  depends on  \( \sigma \)  in addition to d and n.

## I. INTRODUCTION

As is well known, long-range (LR) interactions between spins can affect the critical behavior of magnets. In particular, \( ^{1} \)  if the “exchange” integral decays according to a power law  \( r^{-(d+\sigma)} \) , where r is the distance between spins and d is the dimensionality of the space, the critical exponents and the scaling functions may depend on  \( \sigma \)  in addition to d and the number of components of the spin n. Van der Waals forces in the vapor-liquid transition problem are an example. Whether the system will have a behavior corresponding to short-range (SR) forces, i.e., independent of  \( \sigma \) , or whether the LR force will have an effect on universal quantities depends on the value of  \( \sigma \) . A theorem has been conjectured \( ^{2} \)  and proved in  \( 4-\epsilon \)  dimensions \( ^{3} \)  that the dividing line between LR and SR behaviors is given by  \( \sigma=2-\eta_{SR} \)  where  \( \eta_{SR} \)  is the SR value \( ^{4} \)  of the critical exponent  \( \eta \) . LR behavior will take place if  \( \sigma<2-\eta_{SR} \) ; in this region  \( \eta=2-\sigma \) , independent of d and n, whereas the critical exponent  \( \nu \)  depends on d, n, and  \( \sigma \) . The dividing line between the classical and nonclassical exponents is at d=4 and  \( d=2\sigma \)  for SR and LR forces, respectively (see Fig. 2 below).

While the above statements have been proved only in the  \( \epsilon \)  expansion near d=4, they may be valid more generally. For n>2 there exists an alternative expansion \( ^{5} \)  for dimensions close to d=2. The purpose of this paper is to prove the theorem about the dividing line between SR and LR behavior using the  \( \epsilon \)  expansion around d=2. The method of the proof is similar to that used near d=4. \( ^{3} \)  We set up a system of renormalization-group (RG) recursion relations in the space of Hamiltonians which contain both SR and LR interactions. We will find two fixed points of the recursion relations, one corresponding to each type of the critical behavior. The dividing line  \( \sigma=2-\eta_{SR} \)  is found as the line dividing the domains of attraction of these two fixed points. The line delimiting the region of the existence of the critical point is (for  \( n\geq3 \) ) d=2 and  \( d=\sigma \)  for SR and LR forces, respectively. \( ^{6} \) 

## II. RECURSION RELATIONS

Let \(T\) be the absolute temperature (in energy units), \(d=2+\epsilon\) and \(S_{1}(\vec{\mathbf{x}})\), \(i=1,2,\ldots,n\) components of the spin subject to the condition

 \[ \sum_{i=1}^{n}S_{i}^{2}(\vec{\mathbf{x}})=1,\quad n>2. \quad (1) \] 

The energy functional is given as

 \[ \begin{align*}3C=&-\frac{H}{T}=\frac{a}{2T}\sum_{i=1}^{n}\int d^{4}x S_{i}(\vec{\mathbf{x}})\nabla^{2}S_{i}(\vec{\mathbf{x}})\\&+\frac{b}{2T}\sum_{i=1}^{n}\int d^{4}x S_{i}(\vec{\mathbf{x}})\nabla^{\sigma}S_{i}(\vec{\mathbf{x}}).\end{align*} \quad (2) \] 

The integrals are cut off at short distances (see below). We will consider the case when  \( \sigma \)  is close to 2:  \( 2 - \sigma = O(\epsilon) \) . The operator  \( \nabla^{\sigma} \)  is defined by its Fourier transform

 \[ \nabla^{\sigma}f(\vec{\mathbf{x}})=-\int\frac{d^{4}k}{(2\pi)^{d}}\int d^{4}x^{\prime}e^{i\vec{k}\cdot(\vec{\mathbf{x}}-\vec{\mathbf{x}}^{\prime})}|\vec{k}|^{\sigma}f(\vec{\mathbf{x}}^{\prime}). \quad (3) \] 

Let us eliminate the component  \( S_{n} \)  using Eq. (1). The corresponding terms in the energy are nonlinear in the fields  \( S_{\alpha}, \alpha = 1, 2, \ldots, n - 1 \) ; with  \( S^{2} \equiv \sum_{\alpha=1}^{n-1} S_{\alpha}^{2} \)  we have

 \[ \begin{align*}\int d^{4}x\left[1-S^{2}(\vec{\mathbf{x}})\right]^{1/2}\nabla^{\sigma}[1-S^{2}(\vec{\mathbf{x}})]^{1/2}\\=\int d^{4}x(\frac{1}{4}S^{2}\nabla^{\sigma}S^{2}+\frac{1}{8}S^{4}\nabla^{\sigma}S^{2}+\cdots).\end{align*} \quad (4) \] 

It will turn out that the expectation value of  \( S^{2} \)  is of order  \( \epsilon \)  and we may neglect all terms in the expansion of the square root except those explicitly written in (4).

Going over to the Fourier components we have
 

 \[ -3c=\sum_{\alpha=1}^{n-1}\int\frac{d^{4}k}{(2\pi)^{4}}\frac{ak^{2}+bk^{\alpha}}{T}S_{\alpha}(\vec{k})S_{\alpha}(-\vec{k})+\frac{1}{4}\int\frac{d^{4}k}{(2\pi)^{4}}\frac{ak^{2}+bk^{\alpha}}{T}S^{2}(\vec{k})S^{2}(-\vec{k})+\cdots+\frac{1}{8}\int\frac{d^{4}k}{(2\pi)^{4}}\int\frac{d^{4}p}{(2\pi)^{4}}\frac{ak^{2}+bk^{\alpha}}{T}S^{2}(\vec{k})S^{2}(\vec{p})S^{2}(-\vec{k}-\vec{p})+\cdots, \quad (5) \] 

where

 \[ S^{2}(\vec{k}) \equiv \int S^{2}(x) e^{-i\vec{k} \cdot \vec{x}} d^{4}x = \sum_{\alpha=1}^{n-1} \int \frac{d^{4}p}{(2\pi)^{4}} S_{\alpha}(p) S_{\alpha}(k-p). \] 

After elimination of \(S_{n}\) there appears a Jacobian in the functional integral for the partition function which can be thought of as an effective interaction.\(^{5}\) However, to the first order in \(\epsilon\) to which we are calculating the Jacobian can be ignored. All the wave vector integration regions are restricted to a sphere the radius of which is chosen as a unit of inverse length.

Next the RG recursion relations \( ^{7} \)  will be derived for the system described by the Hamiltonian (5). Let us define a RG transformation by integrating out the fields with wave vectors in the interval  \( \frac{1}{2} > q > 1 \) , followed by rescaling transformation. This operation is denoted by  \( Tr^{*} \) :

 \[ e^{\alpha c^{\prime}\left[S_{\alpha}^{\prime}(\vec{\Omega})\right]}=T r^{*}e^{\alpha c\left[S_{\alpha}(\vec{\Omega})\right]}, \] 

where  \( q' = 2q \in [0, 1] \)  and the fields are rescaled

 \[ S_{\alpha}^{\prime}(\vec{\mathbf{q}}^{\prime})=2^{-(d+2-\eta)/2}S_{\alpha}(\vec{\mathbf{q}}). \] 

The critical exponent  \( \eta \)  in the rescaling factor is determined (in the linear version of the renormalization group, which we are using) by the condition that the repeated application of the RG transformation  \( Tr^{*} \)  leads to a nontrivial fixed point, i.e., for some choice of the parameters the Hamiltonian does not become zero or infinity.

The recursion relations, to first order in  \( \epsilon \)  [a/T and b/T are of order  \( \epsilon^{-1} \) ; see (8) and (13) below] for the coefficients a/T and b/T of  \( k^{2} \)  and  \( k^{\sigma} \)  terms in the Hamiltonian are shown in Fig. 1. The four-point interaction [second term in (5)] is denoted by a heavy wavy line. There is a factor  \( (ak^{2}+bk^{\sigma})/T \)  associated with this interaction line,  \( \vec{k} \)  being the momentum of the line. The solid lines are spin propagators  \( T/(ak^{2}+bk^{\sigma}) \equiv G_{\sigma} \) . In the first recursion relation the first diagram vanishes, because the wavy line carries zero momentum. The second diagram can be evaluated as follows  \( [2-\sigma=O(\epsilon)] \) . For small k, the expression

 \[ \int_{1/2<p<1}\frac{d^{4}p}{(2\pi)^{4}}\frac{a(k-p)^{2}+b\mid k-p\mid^{\alpha}}{a p^{2}+b p^{\alpha}} \] 

depends analytically on k and has an expansion of the form  \( A(\sigma,d)+B(\sigma,d)k^{2}+\cdots \) . Knowing this, and since the diagram is of order 1 (small in comparison to the leading order  \( \epsilon^{-1} \) ), we can put  \( \sigma=2 \) , d=2 and pick the piece which is proportional to  \( k^{2} \) . Thus we get for this diagram the value

 \[ (k^{2}/2\pi)\ln2. \] 

The interaction vertex for the sixth power of the field is denoted by a star with three wavy lines. One of these lines (drawn heavy) carries a factor  \( (ak^{2}+bk^{\alpha})/T=G_{0}^{-1} \) , the other two (drawn light) have a factor of unity associated with them. This asymmetry arises from the way the Hamiltonian (5) is written. It is possible, but not necessary, to symmetrize the diagrammatic technique by replacing  \( ak^{2}+bk^{\alpha} \)  in the last term of (5) by

 \[ \textcircled{1}\{a[k^{2}+p^{2}+(k+p)^{2}]+b(k^{\alpha}+p^{\alpha}+|k+p|^{\alpha})\}. \] 

The first diagram in the second recursion relation has a closed loop which gives the factor  \( (n-1) \) . The second and third diagrams cancel. The sixth diagram cancels one-half of the fifth and this combination gives  \( (k^{2}\ln2)/2\pi \) . The fourth and the seventh diagrams are independent of k because the factors attached to the wavy lines cancel against the propagators. There is one more diagram which is proportional to  \( (ak^{2}+bk^{\alpha})^{2} \)  and has not been drawn. The analytical form of the recursion relations is

 \[ \alpha[k^{2}+b^{\prime}k^{\sigma}]=2^{-2\eta}\left[\frac{\frac{a}{4}k^{2}+\frac{b}{2\delta}k^{\sigma}}{T}+\sum_{i=1}^{i}\frac{1}{T}+\cdots\right] \] 

 \[ \alpha^{\prime}k^{2}+b^{\prime}k^{\sigma}=2^{-2\epsilon-2\eta}\left[\frac{a}{4}k^{2}+\frac{b}{2\delta}k^{\sigma}+(n-1)\right] \] 

![](Sak - 1977 - Low-temperature renormalization group for ferromagnets with long-range interactions-images/1_0.jpg)

FIG. 1. Diagrams contributing to the recursion relations in the first order in  \( \epsilon=d-2 \) . The rules are explained in the main text.
 

 \[ \left(\frac{a}{T}\right)^{\prime}k^{2}+\left(\frac{b}{T}\right)^{\prime}k^{\sigma}=2^{2-\sigma}\eta\left(\frac{1}{4}\frac{a}{T}k^{2}+\frac{1}{2^{\sigma}}\frac{b}{T}k^{\sigma}+\frac{1}{4}\frac{k^{2}}{2\pi}\ln^{2}\right), \quad (6) \] 

 \[ \left(\frac{a}{T}\right)^{\prime}k^{2}+\left(\frac{b}{T}\right)^{\prime}k^{\sigma}=2^{2-\epsilon-2\eta}\left(\frac{1}{4}\frac{a}{T}k^{2}+\frac{1}{2^{\sigma}}\frac{b}{T}k^{\sigma}+(\eta-1)\frac{\frac{1}{4}ak^{2}+(1/2^{\sigma})bk^{\sigma}}{a+b}\frac{\ln2}{2\pi}+\frac{1}{4}k^{2}\frac{\ln2}{2\pi}\right). \quad (7) \] 

The next step is to find the fixed points of the transformations (6) and (7). There is one fixed point corresponding to the SR critical behavior \( ^{5} \) 

 \[ b^{*}=0,\quad(T/a)^{*}=2\pi\epsilon/(n-2). \quad (8) \] 

The value of  \( \eta \)  in this case is

 \[ \eta_{\mathrm{S R}}=\epsilon/(n-2). \quad (9) \] 

To find the value of the critical exponent \(\nu\), we put \(b=0\) and eliminate \(\eta\) between (6) and (7):

 \[ \left(\frac{T}{a}\right)=2^{-\epsilon}\frac{T}{a}\left(1+(n-2)\frac{T}{a}\frac{\ln2}{2\pi}\right). \] 

From this, and from the definition of \(\nu\), which is given by

 \[ \left(\frac{T}{a}\right)^{\prime}-\left(\frac{T}{a}\right)^{*}=2^{1/\nu}\left[\frac{T}{a}-\left(\frac{T}{a}\right)^{*}\right], \] 

we get

 \[ \nu=1/\epsilon+O(1), \] 

which agrees with the previous calculations. \( ^{5} \) 

There is another fixed point, which describes the LR behavior. In this case  \( b \neq 0 \) . Then the  \( k^{\sigma} \)  coefficients of (6) give immediately

 \[ \eta_{\mathrm{L R}}=2-\sigma, \quad (10) \] 

Equating the coefficients of  \( k^{\sigma} \)  of (7) we get

 \[ [T/(a+b)]^{*}=2\pi(d-\sigma)/(n-1). \quad (11) \] 

The  \( k^{2} \)  terms of (7) give, after using (11), (10), and (9),

 \[ (b/a)^{*}=[(n-2)/(d-\sigma)](2-\sigma-\eta_{\mathrm{S R}}). \quad (12) \] 

To get the exponent \(\nu\), we take \(k^{\sigma}\) relations from (6) and (7) and eliminate \(\eta\) from them. This gives

 \[ \left(\frac{T}{b}\right)^{\prime}=2^{-d+\sigma}\left(\frac{T}{b}\right)\left(1+(\pi-1)\frac{T}{b}\frac{b}{a+b}\frac{\ln2}{2\pi}\right). \] 

The exponent \(\nu\) is found by comparing this equation with

 \[ \left(\frac{T}{b}\right)^{\prime}-\left(\frac{T}{b}\right)^{*}=2^{1/\nu}\left[\frac{T}{b}-\left(\frac{T}{b}\right)^{*}\right]. \] 

The result is

 \[ \nu=1/(d-\sigma)+O(1), \] 

which depends on  \( \sigma \) .

We have not yet used the recursion relation for the coefficients of  \( k^{2} \)  in (6) and the question of consistency arises [we have four equations for three unknowns  \( (a/T)^{*} \) ,  \( (b/T)^{*} \) , and  \( \eta \) ]. This last recursion relation leads to

 \[ (T/a)^{*}=2\pi(2-\sigma). \quad (13) \] 

On the other hand, elimination of  \( b^{*} \)  from (11) and (12) also gives (13), so that there are only three independent relations and the consistency of the system (6), (7) is established. One could also write recursion relations for six-point and higher interactions. They would be, however, consequences of (6) and (7). This follows from the symmetry, which allows only two coupling constants T/a and T/b.

## III. STABILITY OF THE FIXED POINTS

Now we perform the linear stability analysis of the fixed points. Let us start by assuming that the critical behavior is determined by the SR fixed point (8). Insert into the Hamiltonian an infinitesimally small perturbation of the form

 \[ \int\frac{d^{4}k}{(2\pi)^{4}}\frac{\delta b}{T}k^{\sigma}S_{\alpha}(k)S_{\alpha}(-k)+\cdots. \] 

The coefficient  \( \delta b/T \)  will be multiplied by some factor at every step of the RG procedure. If this factor is less than unity, the SR fixed point is stable with respect to LR perturbations. In the opposite case we have to assume that the critical behavior of the magnet is determined by the LR fixed point. To find the renormalizing factor for  \( \delta b/T \)  we can use either (6) or (7). It must be irrelevant which equation is used. It is easily checked that the following equation is obtained in either case:

 \[ (\delta b/T)^{\prime}=2^{2-\sigma-\eta_{\mathrm{S R}}\delta b/T}. \quad (14) \] 

Thus, if  \( \eta_{SR}>2-\sigma=\eta_{LR} \) ,  \( \delta b/T \)  returns to zero and we get SR behavior. For  \( \eta_{SR}<\eta_{LR} \) ,  \( \delta b/T \)  grows and the SR fixed point is unstable. This establishes

![](Sak - 1977 - Low-temperature renormalization group for ferromagnets with long-range interactions-images/2_0.jpg)

FIG. 2. Regions of stability of the fixed points for n > 2.
 

the theorem formulated at the beginning of this paper.

The stability of the LR fixed point in LR region is easily established. Indeed, the stability analysis similar to that performed above leads to the recursion relation

 \[ (5a/T)^{\prime}=2^{\sigma-2}5a/T. \] 

Since everywhere in the LR region  \( \sigma<2 \) ,  \( 2^{\sigma-2}<1 \)  and the deviation from the fixed point converges to zero as the renormalization progresses.

The situation is summarized in Fig. 2. There are two classical regions. When  \( \sigma>2 \)  and d>4 the exponents have classical SR values  \( \gamma=\frac{1}{2} \) ,  \( \eta=0 \) . For d>2 \( \sigma \)  and  \( \sigma<2 \) ,  \( \eta=2-\sigma \) ,  \( \nu=\frac{1}{2} \)  (Ref. 1). On the line  \( d=2 \) ,  \( \sigma>2 \)  and  \( d=\sigma \) ,  \( \sigma<2 \)  the critical temperature vanishes. In the region below this line there is no phase transition at nonzero temperatures. In SR region, the critical exponents are determined by the SR fixed point and have nonclassical values, depending only on d and n. Near the lines d=4 and d=2 there exist 4-d and d-2 expansions for the exponents. \( ^{5,7} \)  In the LR region, the LR fixed point is stable and expansions in powers of  \( 2\sigma-d \)  and  \( d-\sigma \)  are available. \( ^{1,6} \)  The dividing line between SR and LR regions has been calculated near both ends. The middle part of this curve is a conjecture. It is very probable that the theorem is valid for all dimensions between 2 and 4 but the proof has not yet been found.

## ACKNOWLEDGMENT

I thank G. Grest for discussions.

 \( ^{*} \) Supported in part by NSF Grant No. DMR 72-03230-A01.

 \( ^{1} \) M. E. Fisher, S. Ma, and B. G. Nickel, Phys. Rev.

Lett. 29, 917 (1972).

 \( ^{2} \) J. F. Nagle and J. C. Bonner, J. Phys. C 3, 352 (1970); G. Stell, Phys. Rev. B 1, 2265 (1970).

 \( ^{3} \) J. Sak, Phys. Rev. B 8, 281 (1973).

 \( ^{4} \) For definitions see, e.g., M. E. Fisher, Rev. Mod. Phys. 46, 597 (1974).

 \( ^{5} \) A. M. Polyakov, Phys. Lett. B 59, 79 (1975); A. A. Migdal, Zh. Eksp. Teor. Fiz. 69, 1457 (1975); E. Brezin and J. Zinn-Justin, Phys. Rev. Lett. 36, 691

(1976); R. A. Pelcovits and D. R. Nelson, Phys. Lett. A 57, 23 (1976).

 \( ^{6} \) E. Brezin, J. Zinn-Justin, and J. C. LeGuillou, J. Phys. A 9, L119 (1976).

 \( ^{7} \) K. G. Wilson and M. E. Fisher, Phys. Rev. Lett. 28, 240 (1972). For reviews, see, e.g., K. G. Wilson and J. Kogut, Phys. Rep. 12, 75 (1974); A. Aharony, in Phase Transitions and Critical Phenomena, Vol. 6, edited by C. Domb and M. S. Green (Academic, New York, 1977); S. Ma, Modern Theory of Critical Phenomena (Benjamin, New York, 1976).
 
