class HangsInC:
    name = "c"

    def algo(self, *a):
        import time

        time.sleep(3600)  # blocks in a C call; SIGALRM-style interrupts would miss this
