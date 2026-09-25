package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input000) throws Exception {
        String left000 = "SELECT * FROM orders WHERE id = '";
        String right000 = "'";
        String value000 = "SELECT * FROM orders WHERE id = ?";
        java.sql.PreparedStatement st = conn.prepareStatement(value000);
        st.setString(1, input000);
        st.executeQuery();
    }
}
