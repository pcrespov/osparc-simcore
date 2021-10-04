/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton class for building Permission table and check doable operations.
 *
 * It implements HRBAC (Hierarchical Role Based Access Control) permission model.
 *
 * It is able to:
 * - add Actions to build a table of permissions
 * - load User's Role from the backend
 * - check whether a role can do a specific actions
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   osparc.data.Permissions.getInstance().canDo("study.start", true)
 * </pre>
 */

qx.Class.define("osparc.data.Permissions", {
  extend: qx.core.Object,

  type : "singleton",

  construct() {
    const initPermissions = osparc.data.Permissions.getInitPermissions();
    for (const role in initPermissions) {
      if (Object.prototype.hasOwnProperty.call(initPermissions, role)) {
        initPermissions[role].forEach(action => {
          this.addAction(role, action);
        }, this);
      }
    }
  },

  statics: {
    ACTIONS: {},

    ROLES: {
      anonymous: {
        can: [],
        inherits: []
      },
      guest: {
        can: [],
        inherits: ["anonymous"]
      },
      user: {
        can: [],
        inherits: ["guest"]
      },
      tester: {
        can: [],
        inherits: ["user"]
      },
      admin: {
        can: [],
        inherits: ["tester"]
      }
    },

    getInitPermissions: function() {
      return {
        "anonymous": [],
        "guest": [
          "studies.templates.read",
          "study.node.data.pull",
          "study.start",
          "study.stop",
          "study.update"
        ],
        "user": [
          "dashboard.read",
          "studies.user.read",
          "studies.user.create",
          "studies.template.create",
          "studies.template.update",
          "studies.template.delete",
          "storage.datcore.read",
          "user.user.update",
          "user.apikey.create",
          "user.apikey.delete",
          "user.token.create",
          "user.token.delete",
          "user.tag",
          "user.organizations.create",
          "study.node.create",
          "study.node.delete",
          "study.node.update",
          "study.node.rename",
          "study.node.start",
          "study.node.data.push",
          "study.node.data.delete",
          "study.node.grouping",
          "study.node.export",
          "study.edge.create",
          "study.edge.delete",
          "study.classifier",
          "study.tag"
        ],
        "tester": [
          "studies.template.create.all",
          "services.all.read",
          "user.role.update",
          "user.clusters.create",
          "study.service.update",
          "study.snapshot.read",
          "study.snapshot.create",
          "study.nodestree.uuid.read",
          "study.filestree.uuid.read",
          "study.logger.debug.read",
          "study.slides",
          "statics.read"
        ],
        "admin": []
      };
    }
  },

  properties: {
    role: {
      check: ["anonymous", "guest", "user", "tester", "admin"],
      init: null,
      nullable: false,
      event: "changeRole"
    }
  },

  members: {
    arePermissionsReady() {
      return this.getRole() !== null;
    },

    getChildrenRoles(role) {
      role = role.toLowerCase();
      const childrenRoles = [];
      if (!this.self().ROLES[role]) {
        return childrenRoles;
      }
      if (!childrenRoles.includes(role)) {
        childrenRoles.unshift(role);
      }
      const children = this.self().ROLES[role].inherits;
      for (let i=0; i<children.length; i++) {
        const child = children[i];
        if (!childrenRoles.includes(child)) {
          childrenRoles.unshift(child);
          const moreChildren = this.getChildrenRoles(child);
          for (let j=moreChildren.length-1; j>=0; j--) {
            if (!childrenRoles.includes(moreChildren[j])) {
              childrenRoles.unshift(moreChildren[j]);
            }
          }
        }
      }
      return childrenRoles;
    },

    __nextAction: function() {
      let highestAction = 0.5;
      for (const key in this.self().ACTIONS) {
        if (highestAction < this.self().ACTIONS[key]) {
          highestAction = this.self().ACTIONS[key];
        }
      }
      return 2*highestAction;
    },

    addAction: function(role, action) {
      if (!this.self().ROLES[role]) {
        return;
      }

      this.self().ACTIONS[action] = this.__nextAction();
      this.self().ROLES[role].can.push(action);
    },

    // https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1#2405
    __canRoleDo: function(role, action) {
      role = role.toLowerCase();
      // Check if role exists
      const roles = this.self().ROLES;
      if (!roles[role]) {
        return false;
      }
      let roleObj = roles[role];
      // Check if this role has access
      if (roleObj.can.indexOf(action) !== -1) {
        return true;
      }
      // Check if there are any parents
      if (!roleObj.inherits || roleObj.inherits.length < 1) {
        return false;
      }
      // Check child roles until one returns true or all return false
      return roleObj.inherits.some(childRole => this.__canRoleDo(childRole, action));
    },

    canDo: function(action, showMsg) {
      let canDo = false;
      if (this.getRole()) {
        canDo = this.__canRoleDo(this.getRole(), action);
      }
      if (showMsg && !canDo) {
        osparc.component.message.FlashMessenger.getInstance().logAs("Operation not permitted", "ERROR");
      }
      return canDo;
    },

    isTester: function() {
      return this.getRole() === "tester";
    }
  }
});
