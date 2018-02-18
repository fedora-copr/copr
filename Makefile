CC=gcc
ARGS=-Wall -g

all: main.o
	${CC} ${ARGS} -o main main.o

main.o: main.c
	${CC} -c main.c

clean:
	rm main *.o
