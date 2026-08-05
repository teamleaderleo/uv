#!/usr/bin/env python3
from __future__ import annotations

import base64
import subprocess
import zlib

PATCH = zlib.decompress(base64.b85decode(
    'c-rk-ZFieE7XI#Ep}Oa!Fvi4AoHx?6Gfii9_w3HJr)g(Cv^|7?9J9f|3P|G3<iGE|k^q6h!D%{^-'
    'K{@3MqFK8T|M_rQapb;CBxylpAu)&Wll<y&Fpf>=)W?b(K!v%Wb@cz=aHF4^MIV)P1Ey3k6x3ViFZcNTz6`k6VIityR++(@o2O=n'
    'e>LkVVBW*gTbKFh~IxthFcS3mki*0kH8}kyHS`#0VPM|hFnGLB8eRrpHh}la@#`^&ree3pJk~Zg<a`}Q$L`gGw;lJm@Z<Pv{4U$n'
    'lcu#WEH>Z%D1?9D_(~Yn>&I3?^cPu4j4$7yP3q)^{2k;;IvGT_-q~O92eXB(}RgS-'
    'Z#yy(f;;$>W)U8aM8$fB|;i|aIEZetn3^6fR!HE+<Za^IZdLBxztV>rOBz;BcQy5k|gyk%Z-A7y2v82tXJ=W;%6s5gvHAVrc>Xt-'
    'Xtd}tF+G3LxoH1q%+I9c?*9Gg5R&Q>Fr@YkP|Lu(G|Quj>42)rv`aPlPpMq0%e};7-JB6vS%FZbA&^e?9x_|W^<$ghaSPt-'
    '%#HlSYVJ}0Iu&!&77z@G02CIQLvOt>M1ma;L-'
    'T5+P_C`<(xqr0c8;3uRib~_?_HJ9l+};zB>NxwLwn&c^m)}>M5@aqyp8C*C}&Qa8#9h;ha<X;KzSqQ5NHq(luVhem?)Vi?=NLC#='
    '_da1JF2qn_iY6c*yOpTvQ)IB}*F^mEu778E6V?DRSXF_dX1@5Q228dQ~$6ON!`$DL6{Ck<SC161x^yng~u^CK#>^QcB|P#Ksn9fJ'
    'Y?5xExz!SA;YO9WR%dx^{ZIK{<z1N6-I=xZ8Nz)$EdK;<;v+uHt_rjF;Nj?(SQVWA(MLqGgwLn|xb%x$u!Kp|-'
    '^F`5yF|KRCIk23#~YOm>8c5aa4APRx(IEokg=iY#Z*_?d1MCsA_{v8|%kt&o6ZHT86J`MTsCY@1+3h51cgU!uN@&kxW0?CA2ISGl'
    'KB%vNjX8@@48F7fZRNT=MKa8`~tc!?J#n~B{HOt&ok?n^>oiA5&E-JVF-'
    '0Y={7cdp8HZ}Q5cq6MF6LMx~M+6*Afod{^F*`{#4Y8xPk<egjV7IxGrT`bRG0#%L^QXM=`7`^4PKGZ;v+ztgAN*V~Kc!E!vVjkf_'
    'cp5S{r59UxOz`-Zcm95#}rUW(ukaaA5@pgAmG|6%R=T^k|Le-?67`*NKRD}6O8Os4&JW~jdL||DNIBwx=+-'
    'ZrYmH+_<5@;nEP+;+$>Aza2+j+wG@ixN_-Qe>wLbUd5f@t_kcW0Qt+;>{zBF9Ni>&COu?~9Qgpd%2{%I@t;oiGHZHe1G-'
    '%SD3FTcV=9hn}2nG)<%#s{Qb`T0#G_Rq9BjE$Mic?tdWD&Zj1O&qedL2hBg_K0BVbv_f;sQIcTS}rU^gtw*egHYZ?@RDtRn&O!%T'
    '0p?fF(((<JEDY8>?p|T+130Vp&L@3%~l}6rqg`D6tzcaLjQOdMLP{FqUR6+6xY=bOF3wM#0<G92mE-b?3>wX2)sbY(Qo=n$MjO-'
    '6)7BB*6ziQLOkOmgTmJ_AWs~1e$kP1}w+irZ@ri0C6ps+eWNw!f|hiw9Uoj3^h~OFvNfts!>-pT3As))1ot^-'
    'ucg$hvKzAB~Q4K(M0v4$Vx1Njg^j;cT@H9=0dY|@;d>;)~XTSvOa`K79*sn_bX)y);TxCG|8=W9lC1CjHVe2$uFSC!$Q}Ec-'
    '(1ntzh+|>E!50cqE?oT2@G}w0?GJqVoEB6Jt)@;wtpE5g`+%Aqw6yV#9E#YGF4vvH)#!PFH?9v&#vT^8w_|HT`8Sf*c*WfNBek1D'
    'k1r39e-U#y#+u<q&!mwHq6?oC$M(SQKre;AZ-'
    'X9bMR9H`?!WN%cF)f8pB%XR0flYd&|CQiZotCv;m=Z(}!Z3c4@_Qn#<ybm~CRmxcx=MwASwlI5x80g=TBCSVx#dF32Ux$lrpTSoE'
    ')y2DBs=XDR1hEUQE#`_avyp4qqk8*d8r>0OF4LN8@<pw^q+h>^{cs%)e<s|f&H@*^W7z||xZs;QWd42-'
    'X5Y2m7#Aj%b#wu$`4mlSyb1jj%Z*@3B<XTD!Z&{vDG_1YpTseNKBmk=hsO33wnw7@d*wvS%uf+VW?j;Low~M=+Lg7cwL4uH!XgJP'
    'e*2mM<)ja(yBK_MR-x4q<Y1O5fh-'
    '!Xk3(NWK$(Gpr=>`x7GY*~tx2W?g!KieKsA)y(Dle|tC0(z;AW?#W%++{5c*Rw;w~a=$y*n|scGoka(t(iWM)Z;O@|GNx7NLG>g^'
    'YBGs>)*?VK=_x8w7Pb;Uv-`ULG!IBxRQRAOkfIpa8n@{Y`r}SeUw|bj-'
    '8rjYc~Q4Dd4X$DS(&lOe1~C=hE#n}zGE`N)8VOU;7@=0q3_m-'
    '3{$+2m!g(T$X^gn3R=5v!eq$6EA@b0^jy1%QZQS<nnYNbkV&j)~sf%|XUoT!?(TP9|EIi*%~Ey6DFe35$z?R?|Cb>!RE{xa-'
    'px9GX72x_-Et>UQ;OMPXu46UvH6TgkSCrPwKLK>4x*I$HJtMU-mtZF~bG-@$_P8(rqk_8z*--'
    'O1kCc?SfycVg>JYC0h}Yf{;ZPT(E6qU0ist}q+&S!D+rH=tE7JFjko*g4}P@+)-({6MGb&PyHv{IFVb-BjH(PnHGc(HCSetK4(<A'
    '(mIZ6{;(9neO>ak<++x|8#}JC}vlK_|mGFahA+-SFMm^4CUB5;Nf_0bYL9Z16qzpoFKpw5*(j{b-'
    'F=P%%(7dK8v8@sVq1a8MaCdxsUp2R@mnoz(B<SJm+D=sAskzOXd3K0;>T4_Zd?~jo2Ab#c1|S&A32C0c(bP8&XQMW{52b4DY4Vw)'
    'w2a(;3UcqY+QdHe|Yh(A(V>(Ayb*3G|{IBprYkm4HghhbrifRd9BIUCHws=&J4#R?jSz%r{RwtpR=dIvtDlmAz~)KQr>FIA`76<+'
    'c0X{-'
    '`V1YN+6+u7qB@K~}{~6%IMUH#97}AXs!8muYP;lz03Jj;Q&<0Y9&oo5{&$?8lo?OqocQYPSvUAeC1Qw!E{wE$Z%3)7%;D9E|tQrn'
    'Kd%!Cee%_YCeL=Nng(5x-`@|BlB6{*_bm;;bgG5ZVg4qWGeCDvtfJ0&^Y6S4}Uv3SB2jZAJlW&-'
    'uA|@*BV`%2EL(&izGu>Z>H`HQ_8voDP-49`@GB*;Uc8Sd@~t=l+dTs-2-'
    '**2+Q)Cc1WUzIyhB<Sj+ZZLdpHjXC@Yd3o2Xb!;&X_>*#|*?3d}L3ncx@v?3gtyIz^Ja=#6?(dIwO>=)|?_hU4K4>+Gc3yRBXs6`'
    'auCYx9JI1bZYXv)47QeF*v*>!kOS`8Z-RZdoy|pQ%6d6OO-ABq{yZ|(ZeS<8&i2c5fd(rdABZ>fr;)Lk_3<t<iZgEs^a3CfQyRT9'
    '!kGq#{Ro5O=eBuZl1TB_OEb=J-m?k|qaHj{}_LQ&grbjO~!z>6otl-MQaal*k2%MX-H5uV0s)2fiNo-Eaizs-'
    '<f~B@Q_i(QUe?wTy(l|?h;7{PNs+4$1C}tERx@CPQ-'
    '$8?ic>=A!#AQb5Kl8&od8A<H($Aa((h||r6ZXfmQk;mUZlr4Z@<|<TC6s8zZ(FuM(fZrwc&nd#1leq+bROHD&rEj)!CdPDoP<F9o'
    '?>4&`85gLuTn}~_OxF<e3TtNmre4rVPC#ch%e=l9=sfxV{_D3kKFjOB@*gL^5TfgT+*od8W4O`#_T_prLg|8Hbqpc2FVa#EBKLQE'
    '>ye;?mi4El*$o+f-9|ZG{DZa{*d*T+KOYuCE_7ocLOC<-'
    'bh)Lrm5oxVAqwlB!%>f)%F+)Tv=9vXNo91_^w1#?x;v<R$f%;Hv}CMPxo2}XpSZQV~l_vIa^qe|7L*~K1&JTz*cK3e&wYU3n-'
    '$*=Q;GK->|`<Ka_BvLNpwUJnXHFW|7t7qyk%SE;N27dRsSqc^LcW*u4U>+yf|0(ib@V{-'
    '_x*D%dR@LjNg0784Ws6h2)xPizE|PvNI9W;l^&Ga3ZZGyPN8uiL3Igs|8KOX4Ff+gP)p4Mz4=OurcYF?oQhP>;<KEJ^q9{$R=SE7'
    'zO)59VO*c?aqtJjkUJ_+B;L;b&V{Ag+yj9P*Z|a4_-'
    '?%>R`m=^)aw(N^U86?JS7;FB(v@2Z*k@Q==!6rS$>&cusA`C%lG0Zo`JS5{_y$I)NuhD;btyJr|pW=;%o6ADy;_6tg5FaqYE`=Jx'
    'q;y|58)o(Vio(+^K`}onK{mVmV!-dg@jA2XXa$jsEYcZ6u@SY~-hi){F!9J)x&2aO<mYCo-JRhH_2_ZXzdh1ij=%xSFAl@d-'
    'ADtTBfo4U_I+VYTm%nd5cTWsQES@<bL<lt{!kX)xh7^|ITb=c_>MVY&Q(QxyLte_WRIP0XN*TnIx2IlyE7vL(<TT!0>sAVN{uhY8'
    'zT!U{I#^r=el_5m8ILm|izAAc7XGZ%r)~I078evT|0m-@zWr8S3;IKm`fdOH9_9pfs2?>Ljr%ya<?pvC{@-a`{{dSo?_>'
)).decode("utf-8")

subprocess.run(
    ["git", "apply", "--whitespace=error-all", "-"],
    input=PATCH,
    text=True,
    check=True,
)
