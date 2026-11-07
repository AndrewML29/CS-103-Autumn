#include <stdio.h>

#define MAX_SIZE 7

int main() {
    int N;
    int A[MAX_SIZE][MAX_SIZE];

    while (scanf("%d", &N) == 1) {
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                scanf("%d", &A[i][j]);
            }
        }

        printf("Введенная матрица:\n");
        for (int i = 0; i < N; i++) {
            for (int j = 0; j < N; j++) {
                printf("%d ", A[i][j]);
            }
            printf("\n");
        }

        printf("Напечатанная строка:\n");

        int top = 0, bottom = N - 1;
        int left = 0, right = N - 1;

        while (top <= bottom && left <= right) {
            for (int i = left; i <= right; i++) {
                printf("%d ", A[top][i]);
            }
            top++;

            for (int i = top; i <= bottom; i++) {
                printf("%d ", A[i][right]);
            }
            right--;

            if (top <= bottom) {
                for (int i = right; i >= left; i--) {
                    printf("%d ", A[bottom][i]);
                }
                bottom--;
            }

            if (left <= right) {
                for (int i = bottom; i >= top; i--) {
                    printf("%d ", A[i][left]);
                }
                left++;
            }
        }

        printf("\n\n");
    }

    return 0;
}
