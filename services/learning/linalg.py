"""Numerically stable pure-Python linear algebra engine for Phase 8.4 LinUCB.

Guarantees 100% self-contained execution without external compiled C dependencies.
Leverages Cholesky decomposition (A = L Lᵀ) for symmetric positive definite matrices,
providing optimal numerical conditioning and exact uncertainty calculation:
    xᵀ A⁻¹ x = ||L⁻¹ x||²
"""

import math
from typing import List, Tuple


def eye(n: int, val: float = 1.0) -> List[List[float]]:
    """Return an n x n identity matrix scaled by val."""
    return [[val if i == j else 0.0 for j in range(n)] for i in range(n)]


def zeros(n: int) -> List[float]:
    """Return an n-dimensional zero vector."""
    return [0.0 for _ in range(n)]


def dot(u: List[float], v: List[float]) -> float:
    """Compute dot product of two vectors."""
    return sum(x * y for x, y in zip(u, v))


def norm(u: List[float]) -> float:
    """Compute Euclidean L2 norm of a vector."""
    return math.sqrt(sum(x * x for x in u))


def outer(u: List[float], v: List[float]) -> List[List[float]]:
    """Compute outer product matrix u vᵀ."""
    return [[x * y for y in v] for x in u]


def mat_vec_mul(A: List[List[float]], x: List[float]) -> List[float]:
    """Compute matrix-vector product A x."""
    return [dot(row, x) for row in A]


def cholesky(A: List[List[float]]) -> List[List[float]]:
    """Compute Cholesky decomposition A = L Lᵀ for symmetric positive-definite matrix A.
    
    Returns lower triangular matrix L.
    """
    n = len(A)
    L = [[0.0 for _ in range(n)] for _ in range(n)]

    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                val = A[i][i] - s
                if val <= 0.0:
                    val = 1e-9  # Numerical regularization floor
                L[i][j] = math.sqrt(val)
            else:
                if L[j][j] == 0.0:
                    L[i][j] = 0.0
                else:
                    L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def solve_lower(L: List[List[float]], b: List[float]) -> List[float]:
    """Solve L y = b by forward substitution."""
    n = len(L)
    y = [0.0 for _ in range(n)]
    for i in range(n):
        s = sum(L[i][k] * y[k] for k in range(i))
        diag = L[i][i]
        y[i] = (b[i] - s) / diag if diag != 0.0 else 0.0
    return y


def solve_upper(U: List[List[float]], b: List[float]) -> List[float]:
    """Solve U x = b by backward substitution, where U is upper triangular."""
    n = len(U)
    x = [0.0 for _ in range(n)]
    for i in range(n - 1, -1, -1):
        s = sum(U[i][k] * x[k] for k in range(i + 1, n))
        diag = U[i][i]
        x[i] = (b[i] - s) / diag if diag != 0.0 else 0.0
    return x


def cholesky_solve(A: List[List[float]], b: List[float]) -> List[float]:
    """Solve A θ = b using Cholesky factorization A = L Lᵀ."""
    L = cholesky(A)
    # 1. Forward substitution: L w = b
    w = solve_lower(L, b)
    # 2. Transpose L to get U = Lᵀ
    n = len(L)
    U = [[L[j][i] for j in range(n)] for i in range(n)]
    # 3. Backward substitution: Lᵀ θ = w
    theta = solve_upper(U, w)
    return theta


def compute_uncertainty(A: List[List[float]], x: List[float]) -> float:
    """Compute sqrt(xᵀ A⁻¹ x) using Cholesky factor L:
    
    Since A = L Lᵀ, xᵀ A⁻¹ x = ||L⁻¹ x||².
    Let y = L⁻¹ x  =>  L y = x (solved by single forward substitution).
    Then sqrt(xᵀ A⁻¹ x) = ||y||₂.
    """
    L = cholesky(A)
    y = solve_lower(L, x)
    return norm(y)
