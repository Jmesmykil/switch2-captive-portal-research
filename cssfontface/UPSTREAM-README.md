# WebKit CSSFontFace Exploit for PS4/PS5

### Vulnerability Scope

|               | CSSFontFace |
| :------------ | :---------- |
| PlayStation 4 | 6.00-13.52  |
| PlayStation 5 | 1.00-13.40  |

### Exploitable In

|               | CSSFontFace |
| :------------ | :---------- |
| PlayStation 4 | 6.00-11.02  |
| PlayStation 5 | 1.00-8.60   |

* PS5 is also exploitable if ASLR can be defeated, either through a heap-shaping trick or a separate leak bug, and the expected vtable pointer can be recovered before the native crash path.

## Supported by This Repository

|               | CSSFontFace | Kernel Exploit |
| :------------ | :---------- |:-------------- |
| PlayStation 4 | 6.00-11.02  | 7.00-11.02     |
| PlayStation 5 | N/A         | N/A            |

* add your payload/hen of choice in public/src named as `payload.bin`
  
## Limitations

* Newer WebKit versions on PlayStation 4 [11.5x-latest] and PlayStation 5 [9.00-latest] redesigned CSSFontFace get/set property handling and introduced `m_propertiesOrCSSConnection`. Because of this and other layout changes, the `m_featureSettings` read/write primitive used by this repository is no longer usable on firmware versions above the ranges listed here.
* On PlayStation 5, vtable checks and WebKit ASLR prevent this repository's chain from working unless a separate ASLR defeat and vtable recovery workaround is found.

Technical writeup: https://linearfox.com/blog/cssfontface-uaf-playstation

# Collaborators / Research References

[ufm42](https://github.com/ufm42): Bug Research, Full Chain Exploit Development.  
[Nathan Fargo](https://github.com/ntfargo) aka @ntfargo: Bug Research, Writeup, Exploit Development.   
[Dr.Yenyen](https://github.com/DrYenyen): Testing.  
Hacking the PS4 by CTurt (2015) https://cturt.github.io/ps4.html    
Old PS5 Webkit contributors. (2022) https://github.com/ChendoChap/PS5-Webkit-Execution
