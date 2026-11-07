#include <stdio.h>

#define MAX_N 8

int main() {
    int n;

    while (scanf("%d", &n) == 1) {
        int a[MAX_N][MAX_N];

        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                scanf("%d", &a[i][j]);
            }
        }

        int min_val = a[0][0];
        int min_col = 0;

        int max_val = a[0][0];
        int max_row = 0;

        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                if (a[i][j] < min_val) {
                    min_val = a[i][j];
                    min_col = j;
                }
                if (a[i][j] > max_val) {
                    max_val = a[i][j];
                    max_row = i;
                }
            }
        }

        for (int i = 0; i < n; i++) {
            a[i][min_col] *= a[max_row][i];
        }

        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                printf("%d ", a[i][j]);
            }
            printf("\n");
        }
    }

    return 0;
}
