#!/usr/bin/env python3
from __future__ import annotations

import base64
import subprocess
import zlib

PATCH = zlib.decompress(base64.b85decode(
    'c-rk-ZFieE7XI#Ep}Oa!Fvi4AoHx?6Gfii9_w3HJr)g(Cv^@?1Ic9@_l_06NlmEW=N&*B1hotFDcDMfE7;$xVb@kjgN%4c(j0}h8'
    'K}y_BkGU!3o7v@%(SKzDqYE0PeDm04=dqo}i;$e%Ow$V@pMD}c6aS2!dEU&nC%#8LZ)evd<I!k$GU*M6!!D!s27^JT5x@VQ47VoM'
    'E*Zf09)U+7_Tq@gAtguTGr5Y{1y5WLpHh}la@|7`Kj0|~&ayO!qpozrSrF35U36wVOqU7eZPWvxri{gmuj4mc`xX~(&Fd&;3pWh@'
    '-72x)0Rx<Qn>?XjFbg~vr)7i0XSbowak0HWJD7OmecRp|?Qf4~-'
    'e}Yb7mYmEBBZg0z{<YB%D%M^Sm}|?%}0cgQyyo`qtld8%1`Yc0p)Q@c<MWj7l$GBkOg;~7jJ>$XE!;7#mfn1v%qm)@spHQS{Lb|#'
    'wBsnx#N6(4Sy_x-!HP+^<h4c8!hMY6}&%=qm+J1E%Ju)EKGp{WuEL<V-'
    'R|>XC3SdghQ9?a;hV3Dv$;odIUdzLw&zvp+$ZHxV|YhbE50SBJUzb!BQ@%uhCeNN8`I{{~ozka|UrFltF~Q2Ec>hH@{XofY&p8b^'
    'O~)i<|_DBm^eZ*IpM$1*#uErOZXaQB~fBdrs9uko<+kS%Obm*JPOl`TSomU$gk1uwHM$Ig})f`mUE!ScsPaPeONj;?5}O=dd>{C`'
    '$B9(@!agp-'
    'r2=m5Wko&{alG1cHuTZ%#FxG;r+=P`Nkp{s}zIkEqbjqguT|Wni&%3<ms1>|Iy{zhAqIORk#sxW|Gd#l?9A^eph{OPWx?Pvk8@<u'
    'uvb+WwiQuJ5L<*6qq=Q4pO&Km0X?R#w1S*knzCQqo*vG$R53!Q=NnWx*viUedGd+#<(e90A#JoGi_cy#bA~1$lRg(xdbJJ2(=eRH'
    'zo(l20dM8tUOyI;RX3(i`*!o12^D2N0QriV3-'
    'LIZ0g3sZY{50P1{BT%s?PaP%aIk}S3BBBE4Db_Qn6GB4F+`+@886>82!71p1dy^`?)rsCA5rd~;J<g{Z#%?#~`fTJl;O=d7=Cy8b'
    'eb~H9P4QCd1TexWoa3LFuER{Te${U|PnLabg@R@9uo+;;ppDPxm^pR0Ehyn86R<*tVc20><@9F33Q{pBG1yqtWCTHLW^<}aMxVFl'
    '&kVVE*q*I<9)-Q<2sZL^pk)5i+`?aBQt~M@(jc7&pi8?b(jm(rkuXP0r|1F%G<47IeM$2+7rJ{urUnS@|pKcibGHT#GAWwJ--qka'
    'o={i1%7mA53IW|d(F85Z#&Cy3|vI(D!%dHO$n)K#Uc^8`b<)12o!2?UPBu9!JghCcCYUmJ1cn7ZH6c(H>Bkz=eVE8~kB{54OC6Q}'
    'bHA}g;zz*z|lK2We5J{9DKo0Qx5<FNHH9q|E(r^i2;VE_fIxb9W{fwk*xy6K77LljYuRc3PXk!CP?8OWma}q~B3N9(Em6^--'
    'g2Osp0B?^`@U}GvCM@i>^AujQ<1}$LAhQ=Q7H))Y6vUH~;6uPQE546qxvrwUOVE&k<_(qst1-'
    '7JPJlf?T+8L2BGwJ*xHn|l=3#P%nkj4;V!$)qsH+++tSF>u(HT<j{O9vS`8t@9N5aS`*S#pRl8Z3KO2^2%>3Vr}VN6Z(I|0KssuA'
    '9C-bFl15K`3tl`@WX&SzrV<XX87Q@3PB(~L#r7trHjq3c3C;WUL-'
    'u=+7fa&#m;l1O_UC!$wIKfAP1d402qv7l~o6=vIrkO|WW1#cO#VK`K^w3{ii0Bs9SS3x?TmJ=xF1ISw#=JQ+xH9B$u)fO5DHZzV1'
    'uHyj4eejs&5M~v%8ymHp33Go~6l0^{W(Ry4UrfPnjNccE>UWa=!nYh}YHFNoK6jl`rMJ>2bX`+#V>e+6rZfdox38CU=0ea{h6W}^'
    'v<#?{<>}=CQN;)*U>Nm9<s8q1?@&%#Me-'
    '%O!%7$zbq|z=P|^>^`x9%tjfIbhayO2rr%)RWIcQ1cg#olr&$1x&Me_5)<@8uIzL0Gg3{?kV=ra3xdIHf9&3jnHXJ}Bys%l9AIS('
    '^)gR9)PI-DhQEiHw29A7FL*4}on+#uBwfOP}Z@*FkIN@H#8>dVqsVt!Zmk_EKe#a&II@T2CSKuAh79Op6X{b}oJo_>^({`HTq37C'
    '_z>e5VPHNUfk<^1+!OYZ%21Bi<mhe&~2)cKWQR60e}w5D~Pm(c8ruGe6YXu&|`YN8*!5-Qr;MkCtZomgADw=<&BfsoZk^pW-QmK>'
    'E9p?_+HjB<&($`cV`H@*`a1a&(RB+4S5AFgI3WtMs`12qqz0lM-'
    '1=k{)}Fm+9tm}k`+t#%d|;8o&}J=YATLRgVdAl9rl3pdyEQ2`B?S_BQui7*(h<ViQP$;)7?8>v_c`<$jSR=ZrpTJ(zxH!&aufQaE'
    'Z&<sJy?7;JeiGIGBgNnJh5czhUO0+N+=~Qub(T^h&77qihVRqEkMY(ry)2A^wG<~j3^Kd=Y_4?PE!sMVfloheDmTe15xl`JJ@>K_'
    'PwCV$jDAnZK#0Eybg9Yg~y3C#JJ#?A7lf7H#9T42!$gMY}X-'
    ';s~q_P*y;T^f6<RXf%FdGV3Wd|BJpmi_1sBVKybH+#HSL#Xlfll?EmplRlQMKgyTy@VPS(cPXUy#A9bI;v}SY7#6sIJXry5}=RPU'
    'ETl(=`sGm|YFxE30BB8K38_S|i68DzJ4R!tvhdz&f}Cv|OLKVTdIpI6fEabc>{zO<@Lo7DL5TS#T^eraCp`KKi3wVV`dR0~G`CoJ'
    'TREzTJi_o$H?qtOfwwWlSA4a%VsnquDbx;{p{0tQqcYC@JllA+{tiqL)tF=Cc}4XB-EQMtnWnQ0W3fZ+BZlZ)f}^(2H}BbO2sl0*'
    'aRpRnQ&l;OqdqlIJ(jRox}5o?R+gY@YZ=1NzL{bS&D}_L}<nnNdLHIqUAOsNMJWM_s{ILxnhXCG?XQW>w5o;gA!2L&K^If<>R=GT'
    'qt><sH9*BWk{IAkOR6W-{MQf@CvJD3i%j?Y6-Ur1gsgH<8zF5!^&BwxuSc9o%&gf5+nj-'
    'P##=aT1f~|7~SjQCd+v^Tz&IUwJNMqqZMkMV`ykDWia-'
    'r{Ywc{{|q6vs3~_aDUdG*lKBbO*qGqXFuhzhrQcm<htls3M$FlGyBFV)lSGAXKfh;6TNlmy?*wE<Six1b+1cPjXC^@MDf<Eb!>q?'
    '{7D7Wrg#tnA$D^C(XfvCRw{M3#`pFn-'
    'v0h**S7a}_6~N(;{)1qw`L8mx;3;@id@#(CId8u@=gkNa2#<XBVqBUr6}AUzxQV62J|*&kT7HnU2-2OhshGq9Q7@-'
    '`XUMXChjyZVxMRN9Ln>byE7ahL$!fXy`O=YIPAVktvqgCx^-'
    'Q9P|wK&auBpwLb=Ez`GF<&#|QiSJ7Q%weR{bWWntK1_0|rIOFFVf;MlCK3A#0Tn<U@uklT*xiV5DHVCmFb__zy$zad~{X_BQsh$n'
    'DXRZ6`6lQ4?0+Ht;9@1ViQ41m^O;u53uAH}hpIxLvx($8HE35V?IOWPCqCQiiAw@3|h^$ZR-2}-'
    '2m_f)k%GWy&0c&nd#1J!J&bdgN`fZ5(0!nDx`C`p0D4aB}_iwh9A6Qvcg>~X(*c&|EqESuCd!oGT=5nrmqI(Rv<$M&eNAEt?A;|k'
    '_T^6W^+T+-'
    ';77!bVI#_T^<MXve0Hbqpc0cnm{EBL`P4{BMC`wD{!rM9`R;mW9N`m=MRKV<!tw&H+rg?NY;*+2=EH%b<*Y32qY*mR|hr;s?Y+U`'
    'MtE63q@T8P4f-'
    '{OXL`$S2z_6kbBA>i0}Zr3_Ma~$a(WAyXM+0uc`HVggeNlL`lv|crd%Pgf>KoRpmWXGd^!`6j)U&4Ke&~O}bzxOekMb;0B3T(Z)F'
    'vMx+b=~mQG3%dW_ZrA@51=(EU*L+Hp?0#YV7GJ#{m0_KOHSlN^mx@gu@Oi<L?5Dr;Y6OyX&A;&%nwn&Zl~H1(qbDdNsP2=W6gp#7'
    '}-'
    '}b{bKZo<N>NeJv2wKBHjJ_gB8oKTwLnkn}fOI?WX(iAeU|!_|<eroLXIhxKrG{Q1@S@gHg9z{;wQK2a#5dwj$TBsAG!&pLDr;3(d'
    '}le{jyE@N{=~CVmXck79`oXu@Q<vNE@K9R0O!$cDj;JBCp{cN2)4P@GD%Ur?HW5wPGqh}>{0kIF?<{bmEVvw<>YA3s>Me|hL^xC('
    'loF>K|;?TfACRt!}vyrYQ)kryu#un#(&Ww`M$RhSTWHy@s<Ng+Fedh0{P=w<NLAl@d-'
    'ADtTBfM!k1I+VYTm%nR1cSj7zESb9zL<l`4!kX)xMiiFdTb=c_>MU`dCjM)X;|=2lB&H%wHQKhIv{7tzG3xoZdaYtYZsWDIZnaS7'
    '|8D4;YyN4WgUMy!SVOU!@h~&8B&K*D;m^u_+J=8%fk6}Ve=;!S`)}oqpFb3--!|ayU`|ko262PYcn@=5{%*VC|E<>bACJ)G1^'
)).decode("utf-8")

subprocess.run(
    ["git", "apply", "--whitespace=error-all", "-"],
    input=PATCH,
    text=True,
    check=True,
)
