public static int cureTheVirus(int n, int[] impact, int[] numOfPre, int[][] precells) {
    // For each cell, compute the total boost if we choose to destroy it
    // (including all prerequisite cells that must also be destroyed)
    int[] costToDestroy = new int[n];
    boolean[] visiting = new boolean[n];
    boolean[] visited = new boolean[n];
    
    for (int i = 0; i < n; i++) {
        computeCost(i, impact, precells, costToDestroy, visiting, visited);
    }
    
    // Greedy approach: choose cells with positive total cost
    // that aren't already included as prerequisites
    boolean[] chosen = new boolean[n];
    int totalBoost = 0;
    
    for (int i = 0; i < n; i++) {
        if (costToDestroy[i] > 0 && !chosen[i]) {
            // Choose to destroy this cell
            addWithPrerequisites(i, chosen, impact, precells);
            totalBoost += costToDestroy[i];
        }
    }
    
    return Math.max(0, totalBoost);
}

private static int computeCost(int cell, int[] impact, int[][] precells, 
                               int[] costToDestroy, boolean[] visiting, boolean[] visited) {
    if (visited[cell]) {
        return costToDestroy[cell];
    }
    
    visiting[cell] = true;
    
    int cost = impact[cell];
    for (int prereq : precells[cell]) {
        cost += computeCost(prereq, impact, precells, costToDestroy, visiting, visited);
    }
    
    visiting[cell] = false;
    visited[cell] = true;
    costToDestroy[cell] = cost;
    
    return cost;
}

private static void addWithPrerequisites(int cell, boolean[] chosen, 
                                        int[] impact, int[][] precells) {
    if (chosen[cell]) {
        return;
    }
    
    chosen[cell] = true;
    
    for (int prereq : precells[cell]) {
        addWithPrerequisites(prereq, chosen, impact, precells);
    }
}