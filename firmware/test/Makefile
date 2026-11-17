# Host unit tests for the proxy packet logic:  make -C hardware/kenwood_proxy/firmware/test
CORE = ../kenwood_proxy
CFLAGS = -std=c99 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -I$(CORE)

test: test_proxy_core
	./test_proxy_core

test_proxy_core: test_proxy_core.c $(CORE)/proxy_core.c $(CORE)/proxy_core.h $(CORE)/config.h
	$(CC) $(CFLAGS) -o $@ test_proxy_core.c $(CORE)/proxy_core.c

clean:
	rm -f test_proxy_core
	rm -rf test_proxy_core.dSYM

.PHONY: test clean
