# -*- coding: utf-8 -*-
'''
    2017
    Margarida Reis & Hugo Silva
    Técnico Lisboa
    IT - Instituto de Telecomunicações

    Made in Portugal

    Acknowledgments: This work was partially supported by the IT – Instituto de Telecomunicações
    under the grant UID/EEA/50008/2013 "SmartHeart" (https://www.it.pt/Projects/Index/4465).
'''

import bitalino


class RepoBIT(bitalino.BITalino):
    def __init__(self, timeout=None):
        self.blocking = True if timeout is None else False
        if not self.blocking:
            try:
                self.timeout = float(timeout)
            except Exception:
                raise Exception(bitalino.ExceptionCode.INVALID_PARAMETER)
        self.wifi = True
        self.serial = False
        self.isBitalino2 = True
