#!/usr/bin/env python3
from __future__ import annotations

import base64
import subprocess
import zlib

PATCH = zlib.decompress(base64.b85decode(
    'c-rk-ZCBek7XF@Jp{D0hd*YY`0s&LnnbMivJ-ajQDecUMwkH@{AzmEYE7?Gn;lJ;_l5ES49Rj5@>~8acCVIKLy7#$nlIjQ3De3pmf|R(MM=m>y'
    '?J)Mv$*K0E)9?2yy`5gKR~_;F_oP1_ZV#+o(i8uV2{idMp^;A`FQA+pl8+riy4gkF4|vLg(<}|*sB1Me_NPHeBX>@ld(%ZiIdt_z7iBDFycjtx'
    'zrv=9?@`R=ZW#O<N&5PpJ?5sAZ^95p|CI%d&S{i#wYM~$hp^FG$8-YN<`vl)`KR>M^QN{v@;&N#JG&kk4hFlUk&@x<l%!~HABPg(8lk-'
    '5uaGtj_Tq@gAq81qlgpT$^ThS=SIRO<ZaSnU$#usS`dE8{P*L0HUZJ&B^rkC&QF$x63w5^*S_cE1d7C_;UN8+j7q?{t$ESB0o#SGAZ@NG7hI_W'
    'XHQ3u8PQAfkEnGCxT#1mz83HSN0xNsg9$=+IHaDLTLQZ&`F^^7CMkznBI|PKsDdDN_I9?ov)I$>7abCTL5kI@h0VppYFr5aD^M)U%tkOD94>T%'
    '?o6a2P`Yrrp5&Ziqo8BDc3%Su^7GFaDQ5>c8Dz(Tv%Cj(q5y<ms#~K3Dqp`KWClC%(vWtn1w243(PyjoJ&)-'
    'nqA6RISUjVM}O357SGO@^qh*7YV3+iiQEJ>rWuR6a&Zq%NE9SLP%;jaPEAo!QxC>cQa6uXXodu@^9V4j3Pg!)={fm9gv<5kLBWE@51ox5jL{Ro'
    'o3usBQbmo_z7BtgFaw~Mzd{wL_`JvfJQ2&2C1r4$tLI^ap@E{@$P1^FCw`o)M6J(Kh*1va#8^Y>CIl?Gj8<X9l+$n|DalSu<raM$p;jrLFAX?{'
    'e3uDvS6fy%-{bqp5#2LvXI;NQ0{<C3Z-J?^m}Nl`g(U_1+a`Z^C+3lKR?##`Gz)716d)YYb4x-'
    '1H!Gnj|pCeX?XI18Js2~cvHbBtyr;NN@t(Wfl9pvG%@nw?qXD2yW*b`&QI^K++1qijw-Tp;)8eE$xPgeVazMO*UMvDk+C@g|*7h63sII=#)!P4'
    'WY<OhQG3T)LbjF6Y!I=?nmMHX|<4RV5rf38ExR?K+FdRg#^8S+mSbHQs*U`hJC&b5@1*=Vq^XJcq3~wXLZx>5ZIrOsJiq9T9Le1**vu)?ACDX@'
    'nDv4Nk+Uh12G4ngU$N#ym?U&7bnd=g%fDOwxZLo26&U>EP#*1u1=Elnr8me703>@4lZ=BE)-geRD$GB%y#xlE&l|{GhHTi-'
    '2pZsD;ckp5i#=*+G9nL{9V}HW=B7TD)6Z8ux0WDr`h6x=)muVQRxn`SnH@u<+l)xjBxM;a#LGbtwfcg!m>w*ZF+I@E1`7?H+l?Q}C{y`9hcRaX'
    'eQ<Y)P?+Q*^m^Vs3^$TH{UlY*e?tG)U5$N#UJq=9hn}2nG)<&5|4{au5nxJg=ccAmIbJiW5*cUqs#s0mkqLy-'
    'H%1LP{caST#$jTp$N_OG$i*9*88$4<H5jegPh=iW(ojd1<%+u<(?+ejOL4wR%U=wcKGtEQ`o<=~rKzAhfXoIrd@(jyZ`V9~qY;tfigH_JYDHSp'
    'aR1QSi1k2PQ1+uKN^TbIonyZh&Vmp3mI~-'
    '6*gpIl&(R*R1#<)N)fr`#M2G2AX$R1}w+irZ@ri0C6qndxBUuq~qR@X`6@18A_(GVTb`Qbfd0Hw6LO(rp07Pz4Nax4`g>RB~OHrQLcMYBqfzF!'
    'Ai%-'
    'r|EKeb8bvb@;d>;HmVWcaXv&mOAu1j|CKV1b<Q=hZE~YrhpAgKqiMz>@(alEppbRJo^YB%Dp>s(COJHm9!aFVjuX*K1FB0=19#0P!eVrbt1#PE'
    'giM%5$au?&4a=dZrQJ-B1V~#@x(w3Uq})KcA3)yRFkj{@sMV1Qh_;Y8kePB!a2*FQ?t{lHmoTfS-Pow*OqlzFQjCp)njP>-'
    'd_DoYF@B$`QNNS?8}@SCsi{$}`P@}PmEKC<&`nLejnjlFn9>wT-'
    'M(JasS81085)=v(K4V)mZz5oL=_{LfML`Zm2*55zC$@}70DOq4l7|?)ICrdLP_5n?v1SBHWof2%H6u2o<eOj<e=p!FASi4a+(F9FOr{EE~iJL@'
    's(`DV5lYtLzmgl^J9pHXx{xIK0|{tR#i(1$a$EV8(ihS)#WUiYiTLG<M>k0pnKcBbc0k&09Gwf%X8E=D~+|atDU8<#Qd)AB@1Y`v%8!^;YaO3f'
    'smAFILc$z$CFlVo_v;({_T%%37C_z>e5VPHNUfk<^1+&OP>9#2M`xC4v_-4i1RDKsC0@bX-(=nEg{(@S+Bq#(Sm`>)x<pL5+WLJqY-WIj;yWSy'
    'BSgGK*(|<`p9~DOAbqm&_A_8M!7^?<cWx|8{dfog1ViEA<80N9xP`hWtRFN3pFpG0lKmOx_ufbrY<QH^Q?NK)lLEfyh{9W=8DBs2rCi_#G2J+;'
    'pS>ODxjgNMbN;U2!r8Lo^(5zybQM18!9wmpV3stYL|;xi+*wLCI+Mc5HTDFnjr|8YtX!9qt~}nP%#%3kssHoL<@6~wJNT4<m1SM#lt{rm}^Swy'
    'gWO&?b8?>nm#wCd9Zra&FXGVU~*9#%8J-nNw$TgJSlBJ`LY8#T=oG)lxp&A;s7H*!GiP~UFOdA7+vP>Xng0q1A^N-dGw|v%?a+BRL-'
    'I~^pQ(S&ZGDev!Q@hPN4AsTKBT^>M_V9CwxeLrJjTz$W%Xh$s<4zRZFhxs(Tj6vK)E%1sTjL_q_fR%bIV6>dIVZ{d}g#X*_j)y24=;yQ@KbNh@'
    '}e@mcPwwc!{;1-AA@I35r7t^IpI%k_yHhFC&^<8!f2w@8ZF6lTz;F;qMig=3L1(MLn>qyMxk<nsey7{vfQXHm?kZ?_>!r~2mts{sJ_SyM-'
    'iJQ>j0X!cCaxIjSxX@+MTic7m@h%E_>n5B<x^I46zGme8-Bfg$(sB{6Lx4SK&w=?__=*2lm)&O2y0*aSEs-Qd4!MO(PN}At5S9O=5J-'
    'ZaLI6U!<2K1SCnOL;1oHfy(I7qPVirRg=H&_>JHB^XOS3<A6Fsovw3Wt2aH#97}AW-@Q)pTbslu!H$j;Q&;fw-?%hsk_136jk?p-'
    'd)Awbur>3{_7Jw*1ra7WKx|ws!_Q`@`|+l(sxIxQ$@#oxyFx#lh8RAf6eBe}}^Y|Jp5iaaWU92yKO2QG8Ln703Blfq5?EtF|9sMxM*l38R3u=i'
    '=U+{{}FNvs6M!P=C>$`f7=KjXB4Ww?pN!2c5g*>^kdMEGo|1bN|LI)$Y(8XJw%U8@+RJzIyis=PgCcO=q2^8gck166IZ|HnGJx;Ga}LZGu-'
    'N5QI195HIU?(K<?*gzt?<-rn9|*S7a|#{0X&;eM-'
    '0w9~3vL;FaP?ONNUw`1*UuU2q^<A^sK35%~5qO^PZ(VLzbFx!|yN|7;i+FcykPZogYsB4ksjwI-'
    'scosd6eWEdNAa987Pq2ps)e%Sa1qWi{V0|sM(zso9tEP6K;*(eCz-XaDspLWavF+W{>E7;W%k_nJH+_1s8D(L(h6YzIj%poP18{EE)@Xo_sCxP'
    'nCV4oi9-'
    '`nI3zkm2xsPWx_#MJpmL^&HgZKpwt2z=N2_=kTM0cF;R39|>m?zMBC#o5_|12)=)Rn>{=YHmLNK52QU)rC@N^v8GevoRI%Qtm+lu)7-'
    '|4vl<6QjFr54XCxM^MdnO6SSM518%EAeb9nfRkiMyi@F&ws<Ci=T%y%%bs@2A0O3(&t;Q(Y}i#j+TaUyr3ak@duR{3`jwkd8&^=rAukRE&*hl<'
    'lT>ZZ?o(9?n=flyM6nu>3<+Jq7oK@g@p3$U=v78)R{$EWjLOvjJ2Sd{)?I2Vt`V08_wl(K2%*xWc+r}sZV-Z9SK4?A=@qM;F%-'
    'CR9FBL2$UOKiZfI{*6gMj$s&pHIj*Yi_tqU~AlI{^kK%bm09LRsO(2t&_L>yr2wUv1CQnCdjVjhSbdeCh+;4mMGxla)qjzb>y)kZVR`gKx)tvB'
    'a}xD&mp8@{@X{d4SI16l3?v?k>XT=9O?P8JpHmJXr&R9uV6jeLrpE}JJd!jMnVrzl~#k!Ld+hVe7=Q`D{7skVf)*ak}yD=phtGouYg_Ek*3Sp6'
    '}1fGSgu%@Hhd_wfE;$?_}Do4OC?VD9+_>LEPHg&PKbHQf<+TbID@1kX6sD_QAa)Ek)pD@U>hOUp)E;p<nFu|<GRx>$azX6MU4I%iUNy8Am5KL+'
    '7Pu|x(mVX|D&%-tPFccmM$VKL*LVU*9@1mY$Xs1ohxlqO&VEI11yH=M`|brDs+*}&awpiJ3^j~4A;9y%Kyj6P%xTe_F~Vk@~5K@|({X<|X-'
    '#q$L0gHEOy9zIMICd3QR$7gDi$u&W}^(kWXBKT?$Z)4_<P7QBCv&Lo}%3sIJ-#4GTCx&B|%-'
    'jefgq{*%&2>g23M%+kXML?YOI+&|&yeSkmx?UaXgh(@7O~aqsh8i%wTcC~jc?c1D}~nnFA!aG#s6$r!{RdVtD!i|c$^7Y5>tG%@MonyZOcEhxS'
    '+B5KN%PD<G1oz&>xD_Z|Cp#Fej)(gSf$HyvKPgf4@WV|4!@r4~EP+{{'
)).decode("utf-8")

subprocess.run(
    ["git", "apply", "--whitespace=error-all", "-"],
    input=PATCH,
    text=True,
    check=True,
)
