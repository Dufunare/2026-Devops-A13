#include <stdio.h>
#include "config.h"
#include "extra.h"

#ifndef MODE
#define MODE 0
#endif

int main(void) { printf("%d\n", VALUE + MODE); return 0; }
