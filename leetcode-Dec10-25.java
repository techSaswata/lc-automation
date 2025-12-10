class Solution {
    public int countPermutations(int[] complexity) {
        long res = 1;
        long mod = 1000000007L;
        int n = complexity.length;
        int base = complexity[0];
        
        for (int i = 1; i < n; i++) {
            if (complexity[i] <= base) {
                return 0;
            }
            res = (res * i) % mod;
        }
        
        return (int) res;
    }
}