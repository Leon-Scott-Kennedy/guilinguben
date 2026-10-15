package com.guilinguben.backend.repository;

import com.guilinguben.backend.model.Role;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

public interface RoleRepository extends JpaRepository<Role, String> {
    /** 种子初始化用：按角色名查角色（幂等创建判断） */
    Optional<Role> findByName(String name);
}
