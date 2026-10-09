CC = cc
CFLAGS = -O2 -Wall -Wextra -DMODE=7
.PHONY: all clean test
all: app
app: main.o
	$(CC) main.o -o app
main.o: main.c config.h
	$(CC) $(CFLAGS) -c main.c -o main.o
test: app
	./app
clean:
	rm -f app main.o
