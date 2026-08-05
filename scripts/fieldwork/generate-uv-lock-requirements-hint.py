#!/usr/bin/env python3
from __future__ import annotations

import base64
import subprocess
import zlib

PATCH = zlib.decompress(base64.b85decode(
    'c-rk-ZCBek7XF@Jp{D0hd*YY?;mwqGrgUa^&+bfnN;~tR?Fq(Kh!@B9N;Z&X`0snKB-'
    '^rM2Se!$yW4ySv3zxPb@kjgN%+BZN`}L;ASLd)$J~_i_3UEE=)ban(K(G$zJBDgv)E4Kc}Pxgr|AWePp`=K*gvJGo;S7avF}mO+u'
    'rfW#%Q!N9`}aBVVBW*gTbKFh~IxthMQw+hYa9*m%t+sdvV0$kdi}kO)g`0&J)+er<7%s-'
    '1Lyd4|vLg(<}|*s4LxY8iX`*=baf3(?vpg8}$IFDPu9?tN2Y<zQx5`@j8mx+zo?&w@U1HzyN37I!~w<OasrwY1tt0>0PLETx{)4_'
    's8DGo^5ZA_O>>r-'
    'e}Yb7mYkuBBZg0z{;M$%AU0cSm}}V^(Tao6CP*Gqmz_T%1`Vb0p)Q@c<MWj7l$GBkOg;~SMP!1XE!;3#mfn%)4*}w@Z*$KTIcD3#'
    'wBsnnd4l)g+CU-'
    '?^oIM<{%%)jTW=`65b!hQA)2;i@c*e3say#naA7K1_(Xgwf6S}!l6rcG0~AW5l90LJ%XRVp}s$`&?3J8T;G+NIo5Szkq;50U?~^W'
    '*Jv!sqw!s}e~;X#IfFP7${@mD1K>gMo8KrM!0Rc#I{NLkMUI1c5&{$IYp)BW0@aUKDRWV9RF!w`o>BD>B!6LXmf(}tHCZG<KL59i'
    'w=DiAtk-'
    '*R4kZbrzU!qF7UFfllh9opyHg7KIp_@wiV{7O^eP20v}yDAa#1P`y2{A0K+uuv&8Vi62ClsUD)%<tKY^$D5f$2bRI4|r3@nz8!GQ'
    'mWy>pA;_gj~7$yL)H_gIjmxHxZso&`RAO%n?EiM$1<oF==QTR+p(_1)Cfx?Q>~3ZgUUhrcG!$_h9Oo2)5NN}5ZIW+dQ0c>2+&EV!'
    'V?YkHcUS>z~;BOp79lZE-YH=t2ACm$|QdUU>j2S-'
    'Ab3e`ee^66MiLp{7nXOy8rdV}6zeSMw$03wr6F(H>OCyC2B^+`GdK%LEqOZ24@j-'
    'CWjlBITCM3gGYPQk2M=B1i!KX84%Le06T!uoTwS2CW%RGiw>)GO(YoOVp8nV}sKa5M#~$rQ%yB+)d&j>a0N;nc!zb2m)^E@W+<rI'
    'P1QdE@hElNTl#zL3q*Gv$2nbIF2~J~7G$F+kqis<!vv&nOY<J-'
    'NO)A#RdTKqX0IateM>UnYxyYpW~^nP)sjI_246{ep;`=p;56*@+swUmF_dYU5Jah*or;s58UV$V~b3Mpv-#-'
    '@>^$j@02@v@F+BDq1M<O@glT`I_M`q6Xdr@{Fh8T|M)KuH)l)u9(=8W0R!la_=PE41KgFoABAV-'
    '1^X<NpB{VcdnUV{;47uJg_uNa;VrrC}i=xh7N&*58x_JV8Qt!@=gc{h7a^AiCGFMiCn{~S<1x)c3`)Z#FyxSNTU1za)93#;K8b>@'
    '!^-3h6?}-PpRwIaba4kXCz(A9VW!Gh&-2m^~DK78yiq!FJ|DFlQ{BGa7ke;&0Mw@99HQ9czcY3x2-uaVPSWjr|_B`r-'
    '`!xnZ0;EcO!J8AfA*29|Epf@k1=jO%?53f`$w<@30J5j=4>70_*|eS}yklv2IAmy(ZH(50f+0Oku+i177GxUDaq|MIlX#&X9WNKV'
    'Kfm*TIxL5k^M2?nRN6T!aZ$I!4}2*UOu8V`7ru2^h9fjqr~1A>vtrkfQ#tlyR(cu8D1v8|6Ao-I5tiGZv9wK#vE7t_$&m(-'
    'd04>c=q2;i2?MBJFjYh+Z1~?7~Ln_01;6g1W_3m~A6MCQKs~yk*3O;ZW7mZYIbAv@JMY2I*{4PN19*Aa8D%FLM#p=*R_BTWB2EOg'
    'SdFjsqC?!DE&~m{ruSt<`cS%>7|ejJ1NB9q>tfJ^{NiexEC<-%0)p-*TL(sd29P+*L}I-b$a)O-;Rx-'
    'GnKa(iBMDzFyO*3qfBQ8kiW-GN4M9r<Vsr6(g8{Vbm9ub37HkLpf~~$rtDjD`8yJJy04#Nk7=w8(SM&Sonx2ck6h13boddgO*fY7'
    '(n~vGz&ssBtNfQPLD+6E7^v@P<0T7F0-'
    'HK#}EzCyoW`6h6ZJ<s+JUx^Dr|vxXOL2!&x%d(o%TG@ui|+?QQqc4N@%uST#T`&r#E?G}gwhzASwu=67{3SwOp8+~pJsKWYvNgrr'
    '2nQ695Cp0uv!$!8hq-'
    '~RZPfH^6vF3m(%^V^$P&Tox3<=#&>fVh}(h!nU*onHw?rBg&rYg*TN3C%9)dIbiF77SFbCi=lEp`zU_G@`AYv9-'
    'B#HzO(?2w84KA6YMN$zf>``lnXND3_?KJP{Fg?K`nSP`497qAcR&!E#1YW~mP{Q1bv9pc~&`w|9euscXu_JgeSlwX?tguM&Ukxne'
    'LC!it0fv1YYdxVf5-'
    '3TU|0B4}Vvgu!qrPr98=UIts;NX1InXEc?u+T|kFqF<c5i2*49L=4A)W(Y!N2cEY~^!j!VD(2!s<lA*B(ZXD$Q^nOqKaNaTJPfpk'
    '*-'
    '=~P<=(+<pT^+O^tmz3gVj_wt6yshlY`n&R>a0iwk<5>PH6+mmmSdIvJWVtRFiKL8yNWx7Np<kGPk#O(Pi$8cki5cKyZ5}x89VdIl'
    ')<z%3d^wcjS_i^C-T=Y$#xr9cbKu*1hb!x(zbP86T2gsVCtFI@Nbx@(2(_)spMF>YhciEGZAaAcI-up1TjRyz;G3U75>t&u5C9##'
    '8&JD;!2KyBfroR>e*-'
    'KFeLTMvgI5U~6B5<K5A|wSNz2xju2j5KBmKd@k1M7D+Li!VLN}hKi@M;8<i#bZW?b^hdkGKHmTaDhA*=i(*E7yA4@7*FP6n4FI^$'
    'm^y0Y&VVjPvuA3?1u6<yGu+!yQra~`Y)N25FP*l{XEmPAI1V0-'
    '_<FXX(glRx&X$DU_Qsb$FU~>I0eEo<C|*8PL3gBsvjgl(p5H)Mb(gSucBy2sdEy%l=rixqv1nh}YvSi;Mgf)QtUEiRcHi9_bp=}u'
    '72?#D&?_&@s+g(5At(5ThGiE7i$1|+y0aI`JAMU6)O_JUoY$+(WWJsR$$FenCX=PwZG&4#>lX=bBd^^exQ$$FON~d{xa%PPZfq3j'
    '*3Q6-lbAgJZ!6P^(u(4lH}=Q+%5xzbwf*=q@?4%y7zHFf7pLO<Hvmzbr4lHD`-}F(R!hTc!a0sS`zeP#=-'
    'nkF*G0!tP)XjN**8w9c0%qrE6XUD=$%XN)w3@oZz)M`dR>}o%;8TYinm^^V+-'
    '`*Pb#1`!GjP8vFme)hIQ1pQmMN&zPCH}_Vz|Qw!OE#yT7xsu}@p>)~w)Fw}y5~k;__JWPqkn-buj@jw5blBrLvKh{EmZM{jy&KyP'
    'CT2}8!vCHIkXm@ELzQQsoVFOr~d;!g8C_K7CIfjs}YKf?hsR2vx8`x%IdgYK);%H#H>Th+A(^_)B)2SJM^l#4u)AKRw;``&cl7c0'
    'B&(~I>e3&Repw{l=y(vdX+$7XGgM|eGIpkGds+m7mr3ErMy>BO7+xC?{7Az)=`lBGY0Cva9(O1%D)Fp9C-'
    'alTXUpuxusfYx8)5~K8=#j%_^ESTid&s+`(hwSM~+Y|XFPQ=i+NDXuO3=TI5N~GfVM72LL`djwKW<U1^s@YEIJel|bv%MLFX`>HN'
    'k^+evh<(!*7a(vaN-JX7(|-BzQFZuSHmPfbef35ozEFpC@N#5t*rUFFm?oBuE0`n6i$fuENuy_CK=4r;v;R~Tx#r8-'
    '6j7}Pq&Z@(;0Mn<sAW0sD-0@>+UCB7E2FaM&(4hgkoA|^iUYzW;vrsS10_`6C|R_osT+h~)0H-'
    '!LgK_~y9WiX9Eam+Aqo$EiyPYQ6D7^cD=7VjfMesiUF!hNaio8Q(a$HR3kNdWEcByiDG^)KdetN@vy@^1Ma%<{9gq4ATNma-'
    '3HK>N!*R&N-p6PbSwAQ$u=VEL5T~6tb;DQ3tbdN(Yaq)#fYzjZfh%r?+R37V-O?fSpNa!7IgwA%(`EC-Mj-hVeTou>6L~hHVHiI%'
    'KSlkzooYi!i*2wZG19V)H4EBcWM9Sfi_ssG2dE15*c`!<bPw+jmMp(=ajE}c4(6V>n;yc0T)1K2SJNGFYIO<XPH^`^-'
    'G7x1M%`}tzj7oUL|Qi5id?^<jx7Rw(#7&EG&>*u(K(aC)7{^h_%SFyiX}3j36tf@%G}*?^jEqe8wNA(8AkccO(1SUaVpV%PH6&0z'
    '=E?Na>I!{Di=}pn+@E}2FjFu<I$r1%R^_wRnUiwVM`}&Uu-'
    '3JVyI%_Jxwf#ym+2~ebC7?!;OcD!i2cH`S?st3fU3Vo1Y>^FM_WI@it-'
    'p=+y8QG;3nkq5O5c{C)Gedtx|d$;^!)Lg*<G)?8;aqOb(t>a4F-'
    'XNmJP@n3@+Zy3)ZF%@a5(Y6Jpjbf{dQ7^yMYZVi68?U8xtA#rMcSGM?@lOjKOfCb*8j9VF$C;5OF~$1`e^&0(HvA(C44Rn#lYt@M'
    'e=BeN{GmwwwgG<+bAm!Nh#QQ?dz}07_uCc!@3gM}0D9HsVg'
)).decode("utf-8")

subprocess.run(
    ["git", "apply", "--whitespace=error-all", "-"],
    input=PATCH,
    text=True,
    check=True,
)
